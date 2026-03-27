# Используем легковесный образ Python
FROM python:3.10-slim

# Устанавливаем системные зависимости, если нужны (например, для gcc)
RUN apt-get update && apt-get install -y gcc

# Рабочая директория
WORKDIR /app

# Копируем файл с зависимостями
COPY requirements.txt .

# Устанавливаем библиотеки
# sdv поставит tensorflow/torch, это займет время при сборке
RUN pip install --no-cache-dir -r requirements.txt

# По умолчанию запускаем bash, чтобы мы могли зайти внутрь
CMD ["bash"]