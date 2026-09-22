set -e

echo "Applying migrations..."
alembic upgrade head

echo "Starting app..."
exec "$@"