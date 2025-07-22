# 🌱 PlantCare REST API

API REST para sistema de monitoreo de plantas con ESP32. Maneja dispositivos IoT, usuarios y datos de sensores.

## 🔗 URLs Base

- **Desarrollo:** `http://localhost:5000`

## 🔓 Autenticación

No requerida

---

## 📍 Endpoints

### 1. Registro de Dispositivos

`POST /api/iot/register`  
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

`POST /api/iot/share`  
Comparte un dispositivo existente con otro usuario.

**Request:**
```json
{
  "udid": "string (requerido)",
  "email": "string (requerido)"
}
```

---

### 3. Obtener Dispositivos de Usuario

`GET /api/iot/{email}`  
Lista todos los dispositivos asociados a un usuario.

---

### 4. Envío de Datos de Sensores

`POST /api/logs/submit`  
Envía datos de sensores desde el dispositivo IoT.

**Request:**
```json
{
  "udid": "string (requerido)",
  "temp": "float (requerido)",
  "moisture_dirt": "float (requerido)",
  "moisture_air": "float (requerido)"
}
```

---

### 5. Consulta de Logs

- **Por dispositivo:**  
  `GET /api/logs/device/{udid}?days=7` (days opcional)

- **Con verificación de usuario:**  
  `GET /api/logs/user-device/{email}/{udid}?days=7` (days opcional)

---

### 6. Desarrollo (Solo local)

`GET /api/devices/debug-list`  
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
  "timestamp": "datetime"
}
```

---

## 🛠 Ejemplos de Uso

**Registrar dispositivo:**
```sh
curl -X POST http://localhost:5000/api/iot/register \
  -H "Content-Type: application/json" \
  -d '{"udid":"ESP32-123", "email":"usuario@ejemplo.com"}'
```

**Obtener logs (7 días):**
```sh
curl "http://localhost:5000/api/logs/user-device/usuario@ejemplo/ESP-123?days=7"
```

**Enviar datos de sensores:**
```sh
curl -X POST http://localhost:5000/api/logs/submit \
  -H "Content-Type: application/json" \
  -d '{"udid":"ESP32-123", "temp":25.5, "moisture_dirt":40, "moisture_air":60}'
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
