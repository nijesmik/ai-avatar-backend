FROM python:3.13-slim AS builder
RUN apt update && apt install -y gcc python3-dev autoconf automake libtool git make wget
WORKDIR /install

# Copy the requirements file into the container
COPY requirements.txt ./

# Install the dependencies
RUN pip install --prefix=/install/deps --no-cache-dir -r requirements.txt

# Install rnnoise
RUN git clone https://gitlab.xiph.org/xiph/rnnoise.git && \
    cd rnnoise && \
    ./autogen.sh && ./configure && make

FROM python:3.13-slim
WORKDIR /backend
COPY --from=builder /install/deps /usr/local

# Copy the rest of the application code into the container
COPY app ./app
COPY --from=builder /install/rnnoise/.libs ./app/rnnoise/libs

ENV RNNOISE_PATH="/backend/app/rnnoise/libs/librnnoise.so"

# Expose the port the app runs on
EXPOSE 8000

# Command to run the application
CMD ["uvicorn", "app.main:sio_app", "--host", "0.0.0.0", "--port", "8000"]
