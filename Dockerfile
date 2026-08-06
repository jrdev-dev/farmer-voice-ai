# Use Python 3.11 slim as the base image
FROM python:3.11-slim

# Install system dependencies required for easyocr and opencv
RUN apt-get update && apt-get install -y \
    libgl1-mesa-glx \
    libglib2.0-0 \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Set up a new user named "user" with user ID 1000
# Hugging Face Spaces require running as a non-root user
RUN useradd -m -u 1000 user

# Switch to the "user" user
USER user

# Set home to the user's home directory
ENV HOME=/home/user \
    PATH=/home/user/.local/bin:$PATH

# Set the working directory
WORKDIR $HOME/app

# Copy the current directory contents into the container at $HOME/app setting the owner to the user
COPY --chown=user:user . $HOME/app

# Install python dependencies
RUN pip install --no-cache-dir -r backend/requirements.txt

# Run Django setup commands (collectstatic, migrate)
RUN cd backend && python manage.py collectstatic --no-input
RUN cd backend && python manage.py migrate

# Expose the port that Hugging Face Spaces expects
EXPOSE 7860

# Start Gunicorn, listening on 0.0.0.0:7860 and changing directory to backend
CMD ["gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:7860", "--chdir", "backend", "--workers", "2", "--threads", "4", "--timeout", "180"]
