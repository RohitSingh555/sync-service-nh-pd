# Sync Service (FastAPI)

This is a lightweight sync service built with **FastAPI**, designed for high-performance asynchronous API endpoints.

## 🔧 Setup Instructions

### 1. Clone and Connect

If you're not already on the server or project directory:

```bash
ssh your-user@your-server-ip
cd ~/fastapi-app/sync-service
```

### 2. Create and Activate Virtual Environment

```bash
python3 -m venv env
source env/bin/activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> Or install manually if `requirements.txt` is not yet created:

```bash
pip install fastapi uvicorn[standard]
```

### 4. Run the FastAPI App

```bash
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

- `main:app` refers to the `app` instance inside your `main.py` file.
- `--reload` is helpful during development for auto-reload.

---

## 📁 Project Structure

```
sync-service/
├── env/                  # Virtual environment
├── main.py               # FastAPI entry point
├── requirements.txt      # Dependencies (optional)
└── README.md             # You're here
```

---

## 📌 Tips

- Access your API at `http://<your-server-ip>:8000`
- Swagger UI available at `http://<your-server-ip>:8000/docs`

---

## 📜 License

MIT License
