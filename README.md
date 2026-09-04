# Appointment Management System (TNS AMS)

Touch & Solve (TNS) Appointment Management System is a Django-based software engineering consultation platform for clients and engineers to schedule, manage, and track consultation sessions.

## 🚀 Features

- **User Roles & Authentication**: Dedicated roles for Clients, Engineers, and Admins.
- **Appointment Scheduling**: Real-time slot selection, booking, and schedule tracking.
- **Dashboard & Analytics**: Role-specific dashboards for managing consultations and requests.
- **Notifications & Feedback**: Built-in notification alerts and post-session client feedback.
- **Service Management**: Customizable service categories and engineer expertise mapping.

## 🛠️ Technology Stack

- **Backend**: Python 3, Django
- **Frontend**: HTML5, CSS3, JavaScript, Bootstrap 5, Crispy Forms
- **Database**: SQLite (default), PostgreSQL / MySQL supported

## ⚙️ Installation & Setup

1. **Clone the Repository**
   ```bash
   git clone https://github.com/afrozaakhi301/Appointment-Management-System1.git
   cd Appointment-Management-System1
   ```

2. **Create and Activate Virtual Environment**
   ```bash
   python -m venv venv
   # On Windows:
   venv\Scripts\activate
   # On macOS/Linux:
   source venv/bin/activate
   ```

3. **Install Dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Setup**
   Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```

5. **Run Migrations**
   ```bash
   python manage.py migrate
   ```

6. **Start the Development Server**
   ```bash
   python manage.py runserver
   ```
   Open `http://127.0.0.1:8000/` in your browser.
