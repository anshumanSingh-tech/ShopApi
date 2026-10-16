set -o errexit

pip install --upgrade pip
pip install -r Requirements.txt
python manage.py collectstatic --no-input
python manage.py migrate --no-input