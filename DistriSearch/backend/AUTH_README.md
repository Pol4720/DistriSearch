# DistriSearch API - Authentication and Tasks

This document describes the new authentication and task management features added to DistriSearch.

## Authentication

The API now includes user authentication with JWT tokens.

### Endpoints

#### POST /auth/register
Register a new user.

**Request Body:**
```json
{
  "username": "string",
  "email": "user@example.com",
  "password": "string"
}
```

**Response:**
```json
{
  "id": 1,
  "username": "string",
  "email": "user@example.com",
  "created_at": "2023-01-01T00:00:00",
  "is_active": true
}
```

#### POST /auth/login
Login and get access token.

**Request Body (form data):**
```
username: string
password: string
```

**Response:**
```json
{
  "access_token": "eyJ0eXAi...",
  "token_type": "bearer"
}
```

#### GET /auth/me
Get current user information. Requires authentication.

**Headers:**
```
Authorization: Bearer <access_token>
```

**Response:** Same as register response.

## Tasks Management

Users can create and manage their tasks.

### Endpoints

#### POST /tasks/
Create a new task. Requires authentication.

**Request Body:**
```json
{
  "title": "string",
  "description": "string (optional)"
}
```

**Response:**
```json
{
  "id": 1,
  "user_id": 1,
  "title": "string",
  "description": "string",
  "status": "pending",
  "created_at": "2023-01-01T00:00:00",
  "updated_at": "2023-01-01T00:00:00"
}
```

#### GET /tasks/
Get all tasks for the current user. Requires authentication.

**Response:** Array of task objects.

#### PUT /tasks/{task_id}
Update task status. Requires authentication and task ownership.

**Request Body:**
```json
{
  "status": "pending|completed|in_progress"
}
```

**Response:** Updated task object.

#### DELETE /tasks/{task_id}
Delete a task. Requires authentication and task ownership.

## Database

A separate SQLite database (`users.db`) stores user and task information, independent of the main search database.

## Security

- Passwords are hashed using PBKDF2
- JWT tokens with 30-minute expiration
- HTTPS support (configure SSL_KEYFILE and SSL_CERTFILE environment variables)

## Environment Variables

- `USER_DATABASE_PATH`: Path to users database (default: `users.db`)
- `SECRET_KEY`: JWT secret key (required)
- `SSL_KEYFILE`: Path to SSL private key for HTTPS
- `SSL_CERTFILE`: Path to SSL certificate for HTTPS