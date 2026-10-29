# start with a lightweight Linux image that has Python 3.11 pre-installed
FROM python:3.11-slim

# create /app folder inside the container and use it as the working directory
WORKDIR /app

# copy requirements.txt first (before the rest of the code) so Docker can
# cache the pip install step — if only code changes, packages won't reinstall
COPY requirements.txt .

# install all required packages into the container
RUN pip install -r requirements.txt

# copy everything else (all code, data folder, etc.) into /app
COPY . .

# set parent directory
ENV PYTHONPATH=/app:/app/dashboard

# command to run when the container starts
# --port=5006 is the port the dashboard runs on
# --address=0.0.0.0 allows connections from outside the container
# CMD ["panel", "serve", "dashboard/final_project_dashboard.py", "--port=5006", "--address=0.0.0.0", "--allow-websocket-origin=*", "--warm"]
CMD ["python", "dashboard/final_project_dashboard.py"]
