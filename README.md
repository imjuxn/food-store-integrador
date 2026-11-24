# Food Store — Trabajo Práctico Integrador de Programación IV

Estudiante: Juan Silva.

Repositorio público: https://github.com/imjuxn/food-store-integrador

Video de demostración (10 a 15 minutos): **PENDIENTE DE GRABAR Y ENLAZAR**.

> Antes de entregar: reemplazar la línea del video por un enlace público real. No incluir el archivo de video dentro del ZIP.

## Funcionalidades

- Catálogo público con búsqueda por nombre, categoría, disponibilidad y paginación en el servidor; estados de carga, vacío y error.
- Registro e inicio de sesión; JWT únicamente en la cookie HttpOnly access_token. Roles user y admin.
- Carrito persistente, checkout con dirección y forma de pago, pedidos propios y cancelación en PENDIENTE.
- Panel con categorías, productos, stock, disponibilidad, pedidos, usuarios y resumen de ventas.
- Descuento de stock y creación del pedido en una sola transacción. Una falla revierte todo.
- Cancelación transaccional con restitución de stock una sola vez. Estados terminales sin cambios.
- Las líneas conservan nombre y precio originales aunque se edite o dé de baja el producto.
- Bajas lógicas de categorías y productos; desactivar una categoría no oculta sus productos ni libera su nombre.

## Requisitos

- Python 3.11, 3.12 o 3.13. No usar Python 3.14 para esta entrega.
- PostgreSQL 15 o posterior, con una base vacía para este proyecto.
- Node.js 20.19+ o 22.12+, y pnpm 9 o posterior. Verificado con Node.js 24 y pnpm 10.
- Dos terminales: una para el backend y otra para el frontend.

No reutilizar la base de los trabajos anteriores: el modelo de este integrador tiene cinco tablas y una sola categoría por producto.

## 1. Backend en Windows / PowerShell

Crear en pgAdmin una base nueva llamada foodstore_integrador. No es necesario crear las tablas manualmente.

Desde la carpeta raíz del proyecto:

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

Editar backend/.env:

1. En DATABASE_URL indicar usuario, contraseña, host, puerto y nombre de la base creada. Si la contraseña tiene caracteres reservados de URL, codificarlos; por ejemplo, @ se escribe %40.
2. Reemplazar SECRET_KEY por una clave aleatoria propia de al menos 32 caracteres. Generarla así:

```powershell
.\.venv\Scripts\python.exe -c "import secrets; print(secrets.token_urlsafe(48))"
```

3. Conservar FRONTEND_ORIGIN=http://localhost:5173 para la ejecución normal.

Ejecutar:

```powershell
.\.venv\Scripts\python.exe -m app.db.check_connection
.\.venv\Scripts\python.exe -m app.db.seed
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

El seed es idempotente: crea el admin, 3 categorías y 8 productos con stock sin duplicarlos ni resetear pedidos o stock existentes.

Cuenta de demostración exigida por la consigna:

- Usuario: admin
- Contraseña: Admin1234!
- Rol: admin

Es una credencial pública de desarrollo; no usarla en producción ni para datos reales.

- API: http://localhost:8000/api/v1
- Swagger: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

La terminal debe quedar abierta. Para detenerla, Ctrl+C.

### Alternativa SQLite para desarrollo

Si no se dispone de PostgreSQL, usar DATABASE_URL=sqlite:///./foodstore.db en el .env y ejecutar el mismo seed. La aplicación permite este modo local, pero los bloqueos de fila para compras concurrentes se verifican con PostgreSQL; no son equivalentes en SQLite.

### Linux / macOS

Los pasos son los mismos. Crear el entorno con python3 -m venv .venv, activarlo con source .venv/bin/activate y ejecutar python -m pip install -r requirements.txt, cp .env.example .env, python -m app.db.seed y uvicorn app.main:app --reload.

## 2. Frontend en otra terminal

Desde la raíz del proyecto:

```powershell
cd frontend
Copy-Item .env.example .env
pnpm install
pnpm build
pnpm dev
```

Abrir http://localhost:5173.

Mantener también esta terminal abierta. pnpm build comprueba TypeScript estricto antes de generar el build.

No mezclar localhost y 127.0.0.1: las cookies y CORS dependen del host. Si se cambia el puerto del frontend, cambiar también FRONTEND_ORIGIN del backend y reiniciarlo. El servidor usa strictPort para no cambiar de puerto silenciosamente si el 5173 está ocupado.

## Variables de entorno

| Archivo | Variable | Uso |
| --- | --- | --- |
| backend/.env | DATABASE_URL | URL PostgreSQL; alternativa local SQLite |
| backend/.env | SECRET_KEY | Firma JWT; aleatoria, mínimo 32 caracteres |
| backend/.env | ALGORITHM | HS256 |
| backend/.env | ACCESS_TOKEN_EXPIRE_MINUTES | 30; expiración del JWT y cookie |
| backend/.env | FRONTEND_ORIGIN | http://localhost:5173; CORS con credenciales |
| backend/.env | COOKIE_SECURE | false en HTTP local; true detrás de HTTPS |
| frontend/.env | VITE_API_URL | http://localhost:8000/api/v1 |

Los .env.example son plantillas sin credenciales locales. Nunca publicar los .env, la clave JWT real ni contraseñas de PostgreSQL. Las variables VITE_* son públicas: no guardar secretos en ellas.

Además de CORS y SameSite=Lax, las operaciones de escritura aceptan el Origin del frontend configurado y el propio origen de la API para Swagger. Se rechazan los demás orígenes. REST Client o scripts locales pueden operar sin ese encabezado.

## Arquitectura

```text
backend/
  app/
    main.py
    core/       config, database, security, deps, base_repository, unit_of_work
    db/         seed y comprobación de conexión
    modules/
      auth/     router y service; reutiliza schemas y modelo de usuarios
      usuarios/ models, schemas, repository, unit_of_work, service, router
      categorias/ misma cadena
      productos/  misma cadena
      pedidos/    misma cadena; su UoW comparte repositorios de pedidos y productos
  tests/        pruebas de integración reproducibles
  requests.http
frontend/
  src/
    features/
      auth/       páginas, API y tipos de sesión
      categorias/ páginas, hooks, API y tipos
      productos/  catálogo, ABM, hooks, API y tipos
      pedidos/    carrito, checkout, pedidos, resumen, componentes, hooks, API y tipos
      usuarios/   administración, hooks y API; reutiliza el tipo Usuario de auth
    shared/
      api/        instancia Axios, errores, interceptores y QueryClient
      components/ layouts, tabla, feedback y encabezados reutilizables
    store/        authStore y cartStore con Zustand + persist
    routes/       AppRouter y ProtectedRoute
    App.tsx       checkSession al montar y renderizado de rutas
```

El router valida HTTP, obtiene permisos y Service con Depends, y convierte excepciones de dominio en HTTPException. El Service abre el UoW y aplica reglas. El Repository consulta la base sin reglas de negocio. El UoW confirma en __exit__; ante cualquier excepción hace rollback y siempre cierra la sesión. Ningún router o service llama a commit.

Los schemas de salida se construyen dentro del UoW, antes de cerrar la sesión. Pedido guarda items con copia histórica de nombre y precio. PostgreSQL bloquea productos y pedidos durante las escrituras; se adquieren los productos en orden de ID para reducir interbloqueos.

TanStack Query maneja catálogo, pedidos, resumen y usuarios. Las mutaciones invalidan sus consultas. TanStack Form controla formularios y TanStack Table las tablas con paginación local. Zustand persiste solo el usuario como pista de interfaz y los ítems del carrito; nunca el token. Una ruta protegida espera la comprobación de /auth/me antes de confiar en la sesión persistida.

## Reglas de pedidos

- PENDIENTE → EN_PREPARACION o CANCELADO.
- EN_PREPARACION → ENTREGADO o CANCELADO.
- ENTREGADO y CANCELADO no admiten transiciones.
- El dueño solo cancela en PENDIENTE. El admin usa el endpoint de estado para avanzar o cancelar cualquier pedido no terminal.
- Cada pedido tiene al menos un ítem, sin productos repetidos; solo vende productos activos, disponibles y con stock suficiente.
- Forma de pago EFECTIVO o TRANSFERENCIA; dirección de 5 a 200 caracteres.
- No hay PUT ni DELETE de pedidos. El total y las líneas son inmutables.

## Comprobación manual

1. Abrir /docs y el catálogo; comprobar las 3 categorías y 8 productos del seed.
2. Registrarse como cliente; agregar 2 unidades de un producto y recargar el carrito.
3. Confirmar un pedido y revisar sus líneas y total en Mis pedidos.
4. En una ventana separada, ingresar como admin y comprobar que el stock bajó en 2.
5. Cancelar el pedido pendiente como cliente y comprobar que el stock vuelve al valor inicial.
6. Con otro pedido, como admin pasar a preparación y luego a entregado; revisar el resumen.
7. Crear, editar y eliminar una categoría y un producto; probar stock y disponibilidad.
8. Activar y desactivar un cliente. El admin no puede desactivarse a sí mismo.
9. Probar errores 400, 401, 403, 404, 409 y 422 con backend/requests.http o Swagger.
10. Probar /admin como cliente y comprobar acceso denegado.

## Pruebas de backend

Desde backend, con las dependencias instaladas:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Usan por defecto una base SQLite separada en backend/.tmp, que se recrea entre casos. Nunca usan DATABASE_URL del .env para borrar datos. Para probar contra PostgreSQL, se puede indicar FOODSTORE_TEST_DATABASE_URL con una base exclusivamente de pruebas: esas tablas se eliminan y recrean. No indicar una base real.

## Formato de entrega

Un único ZIP con backend/, frontend/ y README.md en la raíz, sin node_modules,
.venv, venv, .env, bases de datos ni cachés. Se incluyen las plantillas .env.example.

El repositorio público debe contener el mismo proyecto. El video de demostración
de 10 a 15 minutos se comparte mediante un enlace público en este README; no se
adjunta un archivo MP4 al ZIP.
