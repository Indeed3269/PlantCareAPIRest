# 🌱 PlantCare REST API

API REST para sistema de monitoreo de plantas con ESP32. Maneja dispositivos IoT, usuarios y datos de sensores.

## 🔗 URLs Base

- **Desarrollo:** `http://localhost:5000`

## 🔓 Autenticación

Por implementar

---

## 📍 Endpoints

### 1. Registro de Dispositivos

`POST /iot/register`
Registra un nuevo dispositivo IoT o actualiza su asociación.

**Request:**
```json
{
  "udid": "string (requerido)",
  "email": "string (requerido)"
}
```

**Response (201 Created):**
```json
{
  "message": "Dispositivo registrado",
  "udid": "string",
  "email": "string"
}
```

---

### 2. Compartir Dispositivo

`POST /iot/share`  
Comparte un dispositivo existente con otro usuario.

**Request:**
```json
{
  "udid": "string (requerido)",
  "email_personal": "string (requerido - email del dueño)",
  "email": "string (requerido - email del nuevo usuario)"
}
```
**Response (200 OK):**
```json
{
  "message": "Dispositivo compartido exitosamente"
}
```
---

### 3. Obtener Dispositivos de Usuario

`GET /iot/{email}`  
Lista todos los dispositivos asociados a un usuario.

***Response (200 OK):***
```json
["ESP32-123", "ESP32-456"]
```
---

### 4. Envío de Datos de Sensores

`POST /logs/submit`  
Envía datos de sensores desde el dispositivo IoT.

**Request:**
```json
{
  "udid": "string (requerido)",
  "temp": "float (requerido)",
  "moisture_dirt": "float (requerido)",
  "moisture_air": "float (requerido)",
  "raw_soil": "float (opcional)",
  "soil_type": "integer (opcional)"
}
```
**Response (201 Created):**
```json
{
  "message": "Datos guardados"
}
```
---

### 5. Consulta de Logs

#### Por dispositivo  
`GET /logs/{udid}`

Parámetros opcionales:

  page (int): Número de página (default: 1)

  page_size (int): Elementos por página (default: 10)

  all (bool): Si es true, devuelve todos los registros (ignora paginación)

  since (string): Filtra registros desde esta fecha (formato: YYYY-MM-DDTHH:MM:SS)

  latest (bool): Si es true, devuelve solo el registro más reciente

**Ejemplo:**  
`GET /logs/ESP32-123?page=2&page_size=5`
`GET /logs/ESP32-123?latest=true`
`GET /logs/ESP32-123?since=2023-01-01T00:00:00`

#### Con verificación de usuario  
Mismos parámetros que la versión sin verificación de usuario.
`GET /logs/{email}/{udid}`

**Response (200 OK):**
```json
[{
  "temp": 25.5,
  "moisture_dirt": 40.0,
  "moisture_air": 60.0,
  "raw_soil": 2034.0,
  "soil_type": 1,
  "timestamp": "2023-01-01T12:00:00"
}]
```

**Ejemplo:**  
`GET /logs/usuario@ejemplo.com/ESP32-123?page=2&page_size=5`  
`GET /logs/usuario@ejemplo.com/ESP32-123?latest=true`  
`GET /logs/usuario@ejemplo.com/ESP32-123?since=2023-01-01T00:00:00`

---

### 6. Desarrollo (Solo local)

`GET /iot/debug-list`  
Lista completa de dispositivos y sus relaciones.

---

## 📊 Modelos de Datos

**Dispositivo**
```json
{
  "udid": "string (único)",
  "syncs": ["array de relaciones"],
  "logs": ["array de registros"]
}
```

**Usuario**
```json
{
  "email": "string (único)",
  "created_at": "datetime",
  "syncs": ["array de relaciones"]
}
```

**Log de Sensores**
```json
{
  "temp": "float",
  "moisture_dirt": "float",
  "moisture_air": "float",
  "raw_soil": "float",
  "soil_type": "integer",
  "timestamp": "datetime"
}
```

---

## 🛠 Ejemplos de Uso

**Registrar dispositivo:**
```sh
curl -X POST http://localhost:5000/iot/register \
  -H "Content-Type: application/json" \
  -d '{"udid":"ESP32-123", "email":"usuario@ejemplo.com"}'
```

**Obtener logs (paginados):**
```sh
curl "http://localhost:5000/logs/usuario@ejemplo.com/ESP32-123?page=1&page_size=5"
```

**Enviar datos de sensores:**
```sh
curl -X POST http://localhost:5000/logs/submit \
  -H "Content-Type: application/json" \
  -d '{"udid":"ESP32-123", "temp":25.5, "moisture_dirt":40, "moisture_air":60, "raw_soil":2034, "soil_type":1}'
```

---

## 📋 Códigos de Estado HTTP

| Código | Descripción                  |
|--------|------------------------------|
| 200    | OK - Solicitud exitosa       |
| 201    | Creado - Recurso creado      |
| 400    | Bad Request - Datos inválidos|
| 403    | Forbidden - Sin permisos     |
| 404    | Not Found - Recurso no existe|
| 500    | Error interno del servidor   |

**Cambios Recientes**
- Actualizadas todas las rutas a nuevo formato (/iot/ y /logs/)
- Añadidos campos raw_soil y soil_type a los logs
- Modificado el endpoint de debug legacy para no mostrar emails
- Implementado sistema de paginación en consultas de logs
- Añadida verificación de propiedad en compartir dispositivos

**Rutas antiguas aun presentes**
```json
{
  "GET": [
    "/api/devices/debug-list",
    "/api/iot/<string:email>",
    "/api/logs/device/<string:udid>",
    "/api/logs/user-device/<string:email>/<string:udid>"
  ],
  "POST": [
    "/api/iot/register",
    "/api/iot/share"
  ]
}
```