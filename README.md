# 🌱 PlantCare REST API

API REST para sistema de monitoreo de plantas con ESP32. Maneja dispositivos IoT, usuarios y datos de sensores con rate limiting y soporte para HTTPS.

## 🔗 URLs Base

- **Desarrollo:** `http://localhost:5000`
- **Producción:** `https://your-domain.com` (con redirección automática HTTPS)

## 🔒 Seguridad

- **Rate Limiting:** Implementado por IP con límites por endpoint
- **HTTPS:** Redirección automática en producción
- **Validación:** Verificación de propiedad de dispositivos
- **CORS:** Habilitado para requests cross-origin

### Rate Limits
- **Estricto:** 2 requests/minuto (registro, compartir, logs críticos)
- **Medio:** 5 requests/minuto (debug, gestión de dispositivos)  
- **Suave:** 10 requests/minuto (consulta de logs)

---

## 📍 Endpoints

### 1. Registro de Dispositivos

`POST /iot/register` 🔒 *Strict Rate Limit*  
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

`POST /iot/share` 🔒 *Strict Rate Limit*  
Comparte un dispositivo existente con otro usuario (requiere verificación de propiedad).

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

**Errores:**
- `403 Forbidden`: Usuario no es dueño del dispositivo
- `404 Not Found`: Dispositivo no encontrado

---

### 3. Obtener Dispositivos de Usuario

`GET /iot/{email}` 🔒 *Strict Rate Limit*  
Lista todos los dispositivos asociados a un usuario.

**Response (200 OK):**
```json
["ESP32-123", "ESP32-456"]
```

---

### 4. Envío de Datos de Sensores

`POST /logs/submit` 🔒 *Strict Rate Limit*  
Envía datos de sensores desde el dispositivo IoT.

**Request:**
```json
{
  "udid": "string (requerido)",
  "temp": "float (requerido)",
  "moisture_dirt": "float (requerido)",
  "moisture_air": "float (requerido)",
  "raw_soil": "float (requerido)",
  "raw_calMin": "float (requerido)",
  "raw_calMax": "float (requerido)",
  "soil_type": "integer (requerido)"
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
`GET /logs/{udid}` 🔒 *Mild Rate Limit*

#### Con verificación de usuario  
`GET /logs/{email}/{udid}` 🔒 *Mild Rate Limit*

**Parámetros opcionales:**
- `page` (int): Número de página (default: 1)
- `page_size` (int): Elementos por página (default: 10)
- `all` (bool): Si es `true`, devuelve todos los registros (ignora paginación)
- `since` (string): Filtra registros desde esta fecha (formato: `YYYY-MM-DDTHH:MM:SS`)
- `latest` (bool): Si es `true`, devuelve solo el registro más reciente

**Ejemplos:**  
```bash
GET /logs/ESP32-123?page=2&page_size=5
GET /logs/ESP32-123?latest=true
GET /logs/ESP32-123?since=2023-01-01T00:00:00
GET /logs/usuario@ejemplo.com/ESP32-123?all=true
```

**Response (200 OK):**
```json
[{
  "temp": 25.5,
  "moisture_dirt": 40.0,
  "moisture_air": 60.0,
  "raw_soil": 2034.0,
  "raw_calMin": 1800.0,
  "raw_calMax": 3200.0,
  "soil_type": 1,
  "timestamp": "2023-01-01T12:00:00"
}]
```

---

### 6. Desarrollo (Solo local)

`GET /iot/debug-list` 🔒 *Medium Rate Limit*  
Lista completa de dispositivos, usuarios asociados y conteo de logs.

**Response:**
```json
{
  "devices": [{
    "udid": "ESP32-123",
    "registered_to": "usuario@ejemplo.com",
    "logs_count": 150
  }]
}
```

---

## 📊 Modelos de Datos

**Usuario**
```json
{
  "id": "integer (primary key)",
  "email": "string (único)",
  "created_at": "datetime (Pacific Time)",
  "syncs": ["array de relaciones dispositivo-usuario"]
}
```

**Dispositivo**
```json
{
  "id": "integer (primary key)",
  "udid": "string (único)",
  "syncs": ["array de relaciones usuario-dispositivo"],
  "logs": ["array de registros de sensores"]
}
```

**Log de Sensores**
```json
{
  "id": "integer (primary key)",
  "device_id": "integer (foreign key)",
  "temp": "float",
  "moisture_dirt": "float",
  "moisture_air": "float",
  "raw_soil": "float",
  "raw_calMin": "float",
  "raw_calMax": "float", 
  "soil_type": "integer",
  "created_at": "datetime (Pacific Time)"
}
```

**Sync (Relación Usuario-Dispositivo)**
```json
{
  "user_id": "integer (foreign key, primary key)",
  "device_id": "integer (foreign key, primary key)",
  "created_at": "datetime (Pacific Time)"
}
```

---

## 🛠 Ejemplos de Uso

**Registrar dispositivo:**
```bash
curl -X POST http://localhost:5000/iot/register \
  -H "Content-Type: application/json" \
  -d '{"udid":"ESP32-123", "email":"usuario@ejemplo.com"}'
```

**Compartir dispositivo:**
```bash
curl -X POST http://localhost:5000/iot/share \
  -H "Content-Type: application/json" \
  -d '{
    "udid":"ESP32-123", 
    "email_personal":"dueno@ejemplo.com",
    "email":"amigo@ejemplo.com"
  }'
```

**Obtener logs (últimos 5):**
```bash
curl "http://localhost:5000/logs/usuario@ejemplo.com/ESP32-123?page_size=5"
```

**Obtener último registro:**
```bash
curl "http://localhost:5000/logs/ESP32-123?latest=true"
```

**Enviar datos de sensores:**
```bash
curl -X POST http://localhost:5000/logs/submit \
  -H "Content-Type: application/json" \
  -d '{
    "udid":"ESP32-123", 
    "temp":25.5, 
    "moisture_dirt":40, 
    "moisture_air":60, 
    "raw_soil":2034,
    "raw_calMin":1800,
    "raw_calMax":3200,
    "soil_type":1
  }'
```

---

## 📋 Códigos de Estado HTTP

| Código | Descripción                  |
|--------|------------------------------|
| 200    | OK - Solicitud exitosa       |
| 201    | Creado - Recurso creado      |
| 301    | Redirect - HTTP → HTTPS      |
| 400    | Bad Request - Datos inválidos|
| 403    | Forbidden - Sin permisos     |
| 404    | Not Found - Recurso no existe|
| 429    | Too Many Requests - Rate limit|
| 500    | Error interno del servidor   |

---

## 🔄 API Versionado

### Rutas Actuales (Recomendadas)
```json
{
  "GET": [
    "/iot/debug-list",
    "/iot/{email}",
    "/logs/{udid}",
    "/logs/{email}/{udid}"
  ],
  "POST": [
    "/iot/register",
    "/iot/share", 
    "/logs/submit"
  ]
}
```

### Rutas Legacy (Deprecated pero funcionales)
```json
{
  "GET": [
    "/api/devices/debug-list",
    "/api/iot/{email}",
    "/api/logs/device/{udid}",
    "/api/logs/user-device/{email}/{udid}"
  ],
  "POST": [
    "/api/iot/register",
    "/api/iot/share"
  ]
}
```

**Nota:** Las rutas legacy tienen funcionalidad limitada y serán removidas en futuras versiones.

---

## ⚙️ Configuración

**Variables de Entorno:**
- `DATABASE_URL`: URL de la base de datos (default: SQLite local)
- `PORT`: Puerto del servidor (default: 5000)

**Características:**
- ✅ Rate limiting por IP
- ✅ Migración de base de datos automática  
- ✅ Soporte CORS
- ✅ Redirección HTTPS automática
- ✅ Zona horaria Pacific Time
- ✅ Paginación inteligente
- ✅ Validación de propiedad de dispositivos

---

## 📝 Changelog

**v2.0.0 (Actual)**
- 🆕 Nuevas rutas simplificadas (/iot/ y /logs/)
- 🆕 Campos raw_calMin y raw_calMax añadidos
- 🆕 Rate limiting implementado
- 🆕 Redirección HTTPS automática
- 🆕 Verificación de propiedad en compartir dispositivos
- 🆕 Paginación avanzada con múltiples filtros
- 🆕 Soporte para consultas por fecha (since parameter)
- 🔄 Rutas legacy mantenidas para compatibilidad