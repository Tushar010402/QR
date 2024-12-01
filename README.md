# TRF Manager

A Django-based project for managing Test Request Forms (TRFs) with QR code and barcode functionalities.

## Features

- Generate QR codes for TRF numbers and barcodes for sample tubes
- Each TRF has a unique number and expiry date
- Multiple barcodes can be associated with a single TRF
- Custom expiry dates for barcodes
- Cloud-hosted portal URL redirection on barcode scan
- User authentication and access control
- PostgreSQL database for data storage
- Mobile and desktop compatible interface

## Technical Stack

- Django 5.1.3
- Django REST Framework
- PostgreSQL
- Python QR Code and Barcode libraries
- Bootstrap 5 for UI
- jQuery for AJAX operations

## Installation

1. Clone the repository:
```bash
git clone https://github.com/Tushar010402/QR.git
cd QR
```

2. Create a virtual environment and install dependencies:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

3. Configure PostgreSQL:
```bash
# Create database
createdb trf_db
```

4. Run migrations:
```bash
python manage.py migrate
```

5. Create superuser:
```bash
python manage.py createsuperuser
```

6. Run the development server:
```bash
python manage.py runserver
```

## Usage

1. Access the admin interface at `/admin/`
2. Create TRFs and generate QR codes
3. Add barcodes to TRFs
4. View and manage TRFs and barcodes through the web interface
5. Scan barcodes to access TRF information

## API Endpoints

- `/api/trfs/` - TRF management
- `/api/barcodes/` - Barcode management
- `/api/trf-list/` - TRF list view
- `/api/barcode-list/` - Barcode list view

## License

MIT License