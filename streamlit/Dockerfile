FROM python:3.12-slim

RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    libpq-dev \
    python3-dev \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /workspaces
COPY ./requirements.txt /workspaces
RUN python3 -m pip install --upgrade pip
ARG rerun="8"
RUN python3 -m pip install -r requirements.txt
ARG rerun_app_files="5"
WORKDIR /app
ADD workspaces /app/
COPY workspaces/.env /app/

ENTRYPOINT ["streamlit", "run", "streamlit_app.py", "--server.port=8501", "--server.address=0.0.0.0"]