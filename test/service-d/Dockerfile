FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt
COPY proto/service.proto ./proto/
RUN python -m grpc_tools.protoc -Iproto --python_out=. --grpc_python_out=. proto/service.proto
COPY main.py ./
ENV PORT=8083
EXPOSE 8083
CMD ["python", "main.py"]
