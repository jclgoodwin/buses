FROM python:3.11.0rc2

ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y gdal-bin npm && rm -rf /var/lib/apt/lists/*

WORKDIR /app/

COPY package.json package-lock.json /app/
RUN npm install

RUN pip install poetry

COPY poetry.lock pyproject.toml /app/
RUN poetry install

COPY . /app/
RUN make build-static

ENV SECRET_KEY=f
ENV STATIC_ROOT=/app/staticfiles
RUN poetry run ./manage.py collectstatic --noinput

CMD ["poetry", "run", "gunicorn", "buses.wsgi"]
