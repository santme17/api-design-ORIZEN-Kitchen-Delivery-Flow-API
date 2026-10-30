# ORIZEN Kitchen & Delivery Flow API

![Status](https://img.shields.io/badge/Status-Planning-blue)
![Version](https://img.shields.io/badge/Version-1.0.0-green)

## Descripción del Proyecto

Esta API REST funciona como el motor principal para la gestión de estados, trazabilidad y medición de tiempos operativos en el restaurante ORIZEN. Su objetivo es orquestar el ciclo de vida completo de un pedido, desde que es recibido en caja hasta que el repartidor lo entrega en la puerta del cliente.

El sistema resuelve la opacidad y la ansiedad en el seguimiento de pedidos sustituyendo los tradicionales "tiempos estimados estáticos" por una trazabilidad en tiempo real. Esto se logra mediante el registro de cronómetros por cada proceso (espera en cola, preparación en wok, empaquetado y tránsito), permitiendo tanto al restaurante auditar su eficiencia como al cliente final conocer exactamente qué está pasando con su comida.

## Video de Presentación

- Enlace al video de presentación (máx. 5 minutos): [Ver video en YouTube](https://www.youtube.com/watch?v=SOTZqKKSSVw)

## Equipo de Desarrollo

| Nombre                  | Rol            | GitHub                     |
|-------------------------|----------------|----------------------------|
| Santiago Muñoz Estrada  | Líder / Tester | [@santme17](https://github.com/santme17)                       |
| Juan Jose Rendon Guzman | Backend        | [@JuanR1207](https://github.com/JuanR1207)                     |
| Steeven Grajales Flórez | Analista       | [@stevenflorez2304-oss](https://github.com/stevenflorez2304-oss) |
| Juan Jose Roldan Rivas  | Frontend       | [@majurivas0330-beep](https://github.com/majurivas0330-beep)   |

## Modelo de Datos

El sistema se compone de 8 entidades:

| Entidad              | Descripción |
|----------------------|-------------|
| `USUARIO`            | Cuenta del sistema con rol (cajero, cocina, repartidor, admin). Se usa para autenticación JWT y para registrar quién cambia cada estado. |
| `CLIENTE`            | Persona que realiza pedidos. Evita repetir nombre y teléfono en cada orden. |
| `REPARTIDOR`         | Domiciliario encargado de la entrega. Se asigna al pedido después de crearlo. Soporta borrado lógico. |
| `PRODUCTO`           | Plato o ítem del menú con su precio vigente. |
| `PEDIDO`             | Entidad central. Agrupa cliente, repartidor, modalidad de entrega, estado actual y total. |
| `ITEM_PEDIDO`        | Línea de un pedido: producto, cantidad y precio unitario al momento de la compra. |
| `ESTADO_PEDIDO`      | Historial de transiciones de estado de un pedido (solo se agregan registros, nunca se editan ni se borran). |
| `CRONOMETRO_PROCESO` | Marcas de tiempo de inicio y fin de cada etapa operativa, con la duración calculada por el servidor. |

### Diagrama Entidad-Relación

```mermaid
erDiagram
    CLIENTE ||--o{ PEDIDO : "realiza"
    REPARTIDOR |o--o{ PEDIDO : "entrega"
    PEDIDO ||--|{ ITEM_PEDIDO : "contiene"
    PRODUCTO ||--o{ ITEM_PEDIDO : "se vende en"
    PEDIDO ||--|{ ESTADO_PEDIDO : "registra historial de"
    USUARIO ||--o{ ESTADO_PEDIDO : "realiza el cambio"
    PEDIDO ||--o{ CRONOMETRO_PROCESO : "mide tiempos de"

    USUARIO {
        uuid id PK
        string email UK
        string password_hash
        string rol "ENUM: CAJERO, COCINA, REPARTIDOR, ADMIN"
        boolean activo
        datetime fecha_registro
    }

    CLIENTE {
        uuid id PK
        string nombre
        string telefono
        string email "nullable"
        datetime fecha_registro
    }

    REPARTIDOR {
        uuid id PK
        string nombre
        string telefono
        string vehiculo
        string estado_disponibilidad "ENUM: DISPONIBLE, OCUPADO, INACTIVO"
        datetime fecha_registro
        datetime deleted_at "nullable, soft delete"
    }

    PRODUCTO {
        uuid id PK
        string nombre
        decimal precio "NUMERIC(10,2) COP"
        boolean activo
    }

    PEDIDO {
        uuid id PK
        uuid cliente_id FK
        uuid repartidor_id FK "nullable, se asigna despues de crear"
        string codigo_orden UK
        string tipo_pedido "ENUM: DOMICILIO, RECOGER"
        string direccion_entrega "nullable si es RECOGER"
        string estado_actual "ENUM, copia del ultimo estado"
        decimal total "NUMERIC(10,2) COP"
        datetime fecha_creacion
    }

    ITEM_PEDIDO {
        uuid id PK
        uuid pedido_id FK
        uuid producto_id FK
        int cantidad
        decimal precio_unitario "NUMERIC(10,2), precio al momento de la compra"
    }

    ESTADO_PEDIDO {
        uuid id PK
        uuid pedido_id FK
        uuid usuario_id FK
        string estado "ENUM"
        string observacion "nullable"
        datetime fecha_cambio
    }

    CRONOMETRO_PROCESO {
        uuid id PK
        uuid pedido_id FK
        string nombre_proceso "ENUM: ESPERA_COLA, PREPARACION, EMPAQUETADO, TRANSITO"
        string estado_proceso "ENUM: EN_CURSO, COMPLETADO"
        datetime timestamp_inicio
        datetime timestamp_fin "nullable mientras EN_CURSO"
        int duracion_segundos "nullable, calculado en servidor"
    }
```

### Valores de los ENUM

| Campo                                 | Valores válidos |
|---------------------------------------|-----------------|
| `USUARIO.rol`                         | `CAJERO`, `COCINA`, `REPARTIDOR`, `ADMIN` |
| `REPARTIDOR.estado_disponibilidad`    | `DISPONIBLE`, `OCUPADO`, `INACTIVO` |
| `PEDIDO.tipo_pedido`                  | `DOMICILIO`, `RECOGER` |
| `PEDIDO.estado_actual` y `ESTADO_PEDIDO.estado` | `EN_COLA`, `EN_PREPARACION`, `EMPAQUETADO`, `EN_TRANSITO`, `ENTREGADO`, `CANCELADO` |
| `CRONOMETRO_PROCESO.nombre_proceso`   | `ESPERA_COLA`, `PREPARACION`, `EMPAQUETADO`, `TRANSITO` |
| `CRONOMETRO_PROCESO.estado_proceso`   | `EN_CURSO`, `COMPLETADO` |

### Reglas de Negocio

1. **Transiciones de estado válidas:** `EN_COLA` → `EN_PREPARACION` → `EMPAQUETADO` → `EN_TRANSITO` → `ENTREGADO`. Los pedidos de tipo `RECOGER` omiten `EN_TRANSITO`. `CANCELADO` solo es válido antes de `EN_TRANSITO`. Una transición inválida responde `409 Conflict`.
2. **Historial inmutable:** `ESTADO_PEDIDO` solo admite inserciones. No hay endpoints de edición ni borrado.
3. **Consistencia del estado actual:** al insertar un registro en `ESTADO_PEDIDO`, se actualiza `PEDIDO.estado_actual` en la misma transacción.
4. **Un solo cronómetro activo por proceso y pedido.** Se garantiza con un índice único parcial en PostgreSQL:
   ```sql
   CREATE UNIQUE INDEX uq_cronometro_activo
   ON cronometro_proceso (pedido_id, nombre_proceso)
   WHERE timestamp_fin IS NULL;
   ```
5. **Duración calculada en servidor:** `duracion_segundos` se calcula al cerrar el cronómetro como `timestamp_fin - timestamp_inicio`. Nunca se recibe del cliente.
6. **Total verificable:** `PEDIDO.total` debe ser igual a la suma de `cantidad * precio_unitario` de sus ítems. El servidor lo calcula; el cliente no lo envía.
7. **Precio congelado:** `ITEM_PEDIDO.precio_unitario` guarda el precio al momento de la compra, de modo que cambios posteriores en `PRODUCTO.precio` no alteran pedidos existentes.
8. **Asignación de repartidor:** solo pedidos `DOMICILIO` pueden tener repartidor, y solo repartidores con estado `DISPONIBLE`. Al asignarlo pasa a `OCUPADO`.
9. **Dirección obligatoria** para pedidos `DOMICILIO`; opcional para `RECOGER`.
10. **Borrado lógico:** los repartidores se marcan con `deleted_at`. Los pedidos no se borran; se cancelan mediante un estado.

## Documentación de Endpoints (API Design)

Endpoints diseñados bajo estándares RESTful. Base URL propuesta: `http://api.orizen.com/v1`

Todos los endpoints, excepto `POST /auth/login`, requieren el header `Authorization: Bearer <token>`.

### 0. Autenticación

| Método | Endpoint       | Descripción                  | Payload (Body)                                  | Respuesta Esperada |
|--------|----------------|------------------------------|-------------------------------------------------|--------------------|
| POST   | `/auth/login`  | Iniciar sesión y obtener JWT | `{ "email": "...", "password": "..." }`         | 200 OK (token)     |

### 1. Recurso: Clientes (`/customers`)

| Método | Endpoint          | Descripción                | Payload (Body)                                    | Respuesta Esperada |
|--------|-------------------|----------------------------|---------------------------------------------------|--------------------|
| GET    | `/customers`      | Listar clientes            | N/A                                               | 200 OK (Array)     |
| GET    | `/customers/:id`  | Obtener un cliente         | N/A                                               | 200 OK (Object)    |
| POST   | `/customers`      | Registrar un cliente       | `{ "nombre": "...", "telefono": "..." }`          | 201 Created        |
| PUT    | `/customers/:id`  | Actualizar datos           | `{ "telefono": "..." }`                           | 200 OK             |

### 2. Recurso: Productos (`/products`)

| Método | Endpoint          | Descripción                           | Payload (Body)                          | Respuesta Esperada |
|--------|-------------------|---------------------------------------|-----------------------------------------|--------------------|
| GET    | `/products`       | Listar productos                      | N/A                                     | 200 OK (Array)     |
| GET    | `/products/:id`   | Obtener un producto                   | N/A                                     | 200 OK (Object)    |
| POST   | `/products`       | Crear un producto                     | `{ "nombre": "...", "precio": 0.0 }`   | 201 Created        |
| PUT    | `/products/:id`   | Actualizar producto                   | `{ "precio": 0.0, "activo": true }`    | 200 OK             |

### 3. Recurso: Repartidores (`/couriers`)

| Método | Endpoint          | Descripción                       | Payload (Body)                           | Respuesta Esperada |
|--------|-------------------|-----------------------------------|------------------------------------------|--------------------|
| GET    | `/couriers`       | Listar repartidores               | N/A                                      | 200 OK (Array)     |
| GET    | `/couriers/:id`   | Obtener un repartidor             | N/A                                      | 200 OK (Object)    |
| POST   | `/couriers`       | Registrar un repartidor           | `{ "nombre": "...", "vehiculo": "..." }` | 201 Created        |
| PUT    | `/couriers/:id`   | Actualizar datos del repartidor   | `{ "estado_disponibilidad": "..." }`     | 200 OK             |
| DELETE | `/couriers/:id`   | Eliminar repartidor (soft delete) | N/A                                      | 204 No Content     |

### 4. Recurso: Pedidos (`/orders`)

| Método | Endpoint                | Descripción                                   | Payload (Body)                                                                                  | Respuesta Esperada |
|--------|-------------------------|-----------------------------------------------|-------------------------------------------------------------------------------------------------|--------------------|
| GET    | `/orders`               | Listar pedidos (filtros: estado, fecha, tipo) | N/A                                                                                             | 200 OK (Array)     |
| GET    | `/orders/:id`           | Obtener un pedido                             | N/A                                                                                             | 200 OK (Object)    |
| POST   | `/orders`               | Crear un pedido con sus ítems                 | `{ "cliente_id": "...", "tipo_pedido": "DOMICILIO", "direccion_entrega": "...", "items": [{ "producto_id": "...", "cantidad": 2 }] }` | 201 Created        |
| PUT    | `/orders/:id`           | Actualizar datos del pedido                   | `{ "direccion_entrega": "..." }`                                                                | 200 OK             |
| PATCH  | `/orders/:id/courier`   | Asignar repartidor al pedido                  | `{ "repartidor_id": "..." }`                                                                    | 200 OK             |
| POST   | `/orders/:id/cancel`    | Cancelar el pedido                            | `{ "observacion": "..." }`                                                                      | 200 OK             |

El `total` y el `estado_actual` inicial (`EN_COLA`) los define el servidor al crear el pedido.

### 5. Endpoints Anidados de Pedido

| Método | Endpoint                       | Descripción                                          | Payload (Body)                                  | Respuesta Esperada |
|--------|--------------------------------|------------------------------------------------------|-------------------------------------------------|--------------------|
| GET    | `/orders/:id/items`            | Listar los ítems de un pedido                        | N/A                                             | 200 OK (Array)     |
| GET    | `/orders/:id/statuses`         | Historial de estados de un pedido                    | N/A                                             | 200 OK (Array)     |
| POST   | `/orders/:id/statuses`         | Registrar un nuevo estado (valida la transición)     | `{ "estado": "EN_PREPARACION", "observacion": "..." }` | 201 Created  |
| GET    | `/orders/:id/process-timers`   | Cronómetros asociados a un pedido                    | N/A                                             | 200 OK (Array)     |
| POST   | `/orders/:id/process-timers`   | Iniciar un cronómetro para un proceso del pedido     | `{ "nombre_proceso": "PREPARACION" }`           | 201 Created        |
| GET    | `/couriers/:id/orders`         | Pedidos asignados a un repartidor                    | N/A                                             | 200 OK (Array)     |

El historial de estados es append-only: no existen `PUT` ni `DELETE` sobre estados.

### 6. Recurso: Cronómetros de Proceso (`/process-timers`)

| Método | Endpoint                      | Descripción                                    | Payload (Body) | Respuesta Esperada |
|--------|-------------------------------|------------------------------------------------|----------------|--------------------|
| GET    | `/process-timers`             | Listar cronómetros (filtros: pedido, proceso)  | N/A            | 200 OK (Array)     |
| GET    | `/process-timers/:id`         | Obtener un cronómetro                          | N/A            | 200 OK (Object)    |
| PATCH  | `/process-timers/:id/stop`    | Detener el cronómetro y calcular la duración   | N/A            | 200 OK             |

### Códigos de Error Comunes

| Código | Uso |
|--------|-----|
| 400 Bad Request          | Cuerpo mal formado |
| 401 Unauthorized         | Token ausente o inválido |
| 403 Forbidden            | El rol del usuario no tiene permiso para la acción |
| 404 Not Found            | El recurso no existe |
| 409 Conflict             | Transición de estado inválida, cronómetro ya activo, repartidor no disponible |
| 422 Unprocessable Entity | Falla de validación (Pydantic) |

## Stack Tecnológico Propuesto

| Componente     | Tecnología |
|----------------|------------|
| Lenguaje       | Python |
| Framework      | FastAPI |
| Base de datos  | PostgreSQL |
| Autenticación  | JWT (JSON Web Tokens) |
| Validación     | Pydantic |
| Contenedores   | Docker Compose |

## Roadmap / Próximos Pasos

1. Configurar el entorno de desarrollo local con Docker Compose.
2. Crear las migraciones de base de datos basadas en el modelo ER (incluido el índice único parcial de cronómetros).
3. Implementar autenticación JWT y control de acceso por rol.
4. Implementar controladores y validaciones Pydantic para los endpoints GET y POST.
5. Implementar la máquina de estados de pedidos y las reglas de negocio.
6. Escribir pruebas (Postman y pytest) para los casos válidos e inválidos de transición.

## Enlaces

- Repositorio GitHub: [santme17/api-design-ORIZEN-Kitchen-Delivery-Flow-API](https://github.com/santme17/api-design-ORIZEN-Kitchen-Delivery-Flow-API)
- Video de presentación: [Ver video en YouTube](https://www.youtube.com/watch?v=SOTZqKKSSVw)
- Organización del equipo: [Reemplazar con enlace a Trello/Jira](#)
