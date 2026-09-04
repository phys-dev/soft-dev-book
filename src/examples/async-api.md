# Асинхронное API для кинотеатра

Каталог фильмов в пособии по физике требует объяснения. Задача здесь та же самая, что в электронном журнале эксперимента, в портале выдачи данных или в системе управления установкой. По идентификатору достать запись, заглянув сначала в кеш, а потом в хранилище, и отдать её по HTTP, никого при этом не заставив ждать. Смени существительные, поставив вместо фильма выстрел, а вместо жанра тип детектора, и перед тобой сервис, отдающий данные твоего эксперимента.

Посторонняя предметная область взята нарочно. Когда в примере есть пучок, внимание уходит на пучок, а устройство программы остаётся незамеченным. Здесь физики нет, и смотреть приходится на архитектуру, на слои, асинхронный ввод-вывод, кеш и работу с внешними хранилищами. Она же лежит под главой про [цифрового двойника](./accumulator.md), где наружу выставляются каналы EPICS, и под главой про [помощника оператора](./sava.md), где сервисы общаются через очереди.

Устроено это так. Данные лежат в полнотекстовом поисковом движке Elasticsearch, а частые ответы кешируются в Redis, чтобы не дёргать поиск лишний раз. Всё общение с внешними хранилищами асинхронное, и пока один запрос ждёт ответа от базы, сервис обслуживает десятки других. Механику `async`/`await` мы разбирали в главе про [асинхронность](../perf/async.md).

## Структура проекта

Проект разбит на слои, и это главное, на что стоит смотреть в примере. Каждый каталог отвечает за одну задачу.

```
project/
├── Dockerfile
├── requirements.txt
├── src/
│   ├── main.py
│   ├── api/
│   │   └── v1/
│   │       └── film.py
│   ├── core/
│   │   ├── config.py
│   │   └── logger.py
│   ├── db/
│   │   ├── elastic.py
│   │   └── redis.py
│   ├── models/
│   │   └── film.py
│   └── services/
│       └── film.py
```

Такое разделение называют слоистой (луковичной) архитектурой, в которой `api` знает про `services`, `services` знает про `db` и `models`, но не наоборот. Благодаря этому источник данных можно заменить, не трогая ни одного обработчика HTTP-запросов, например перевести сервис с Elasticsearch на PostgreSQL, переписав только слой `db`.

## Основные зависимости

```txt
aioredis==1.3.1
elasticsearch[async]==7.9.1
fastapi==0.61.1
orjson==3.4.1
uvicorn==0.12.2
uvloop==0.14.0
```

Ядром служит **FastAPI**, асинхронный веб-фреймворк, сам генерирующий документацию к API из аннотаций типов. Запускает его сервер `uvicorn`, `uvloop` даёт быструю замену стандартного цикла событий, а `orjson` быстрый сериализатор JSON. Клиенты к Redis и Elasticsearch взяты в асинхронных версиях, потому что обычные, блокирующие, остановили бы весь цикл событий на время запроса.

## Конфигурация

**core/config.py:**

```python
import os
from logging import config as logging_config
from core.logger import LOGGING

logging_config.dictConfig(LOGGING)

PROJECT_NAME = os.getenv('PROJECT_NAME', 'movies')
REDIS_HOST = os.getenv('REDIS_HOST', '127.0.0.1')
REDIS_PORT = int(os.getenv('REDIS_PORT', 6379))
ELASTIC_HOST = os.getenv('ELASTIC_HOST', '127.0.0.1')
ELASTIC_PORT = int(os.getenv('ELASTIC_PORT', 9200))
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
```

Все настройки читаются из переменных окружения со значениями по умолчанию для локальной разработки. Это [12-факторный подход](https://12factor.net/config), при котором один и тот же образ приложения работает и на ноутбуке, и в продакшене, а меняются только переменные окружения, а не код.

## База данных

**db/elastic.py:**

```python
from typing import Optional
from elasticsearch import AsyncElasticsearch

es: Optional[AsyncElasticsearch] = None

async def get_elastic() -> AsyncElasticsearch:
    return es
```

**db/redis.py:**

```python
from typing import Optional
from aioredis import Redis

redis: Optional[Redis] = None

async def get_redis() -> Redis:
    return redis
```

Здесь заводятся глобальные соединения с хранилищами. Модуль хранит объект клиента, а функции `get_elastic()`/`get_redis()` его отдают, и позже эти функции подставит механизм зависимостей FastAPI. Пока приложение не запущено, оба клиента равны `None`, поэтому тип помечен как `Optional`.

## Основное приложение

**main.py:**

```python
import logging
import aioredis
import uvicorn
from elasticsearch import AsyncElasticsearch
from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from api.v1 import film
from core import config
from core.logger import LOGGING
from db import elastic, redis

app = FastAPI(
    title=config.PROJECT_NAME,
    docs_url='/api/openapi',
    openapi_url='/api/openapi.json',
    default_response_class=ORJSONResponse,
)

@app.on_event('startup')
async def startup():
    redis.redis = await aioredis.create_redis_pool(
        (config.REDIS_HOST, config.REDIS_PORT),
        minsize=10,
        maxsize=20
    )
    elastic.es = AsyncElasticsearch(
        hosts=[f'{config.ELASTIC_HOST}:{config.ELASTIC_PORT}']
    )

@app.on_event('shutdown')
async def shutdown():
    await redis.redis.close()
    await elastic.es.close()

app.include_router(film.router, prefix='/api/v1/film', tags=['film'])

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)
```

Точка входа. Соединения с базами создаются в обработчике события `startup` и аккуратно закрываются в `shutdown`, так как открывать их на каждый запрос было бы расточительно, и потому используется пул соединений (`minsize=10, maxsize=20`). Обработчики запросов подключаются роутером с префиксом `/api/v1/`, а версия в URL позволит потом выпустить `v2`, не сломав уже написанных клиентов.

## API слой

**api/v1/film.py:**

```python
from http import HTTPStatus
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from services.film import FilmService, get_film_service

router = APIRouter()

class Film(BaseModel):
    id: str
    title: str

@router.get('/{film_id}', response_model=Film)
async def film_details(
    film_id: str, 
    film_service: FilmService = Depends(get_film_service)
) -> Film:
    film = await film_service.get_by_id(film_id)
    if not film:
        raise HTTPException(
            status_code=HTTPStatus.NOT_FOUND, 
            detail='film not found'
        )
    return Film(id=film.id, title=film.title)
```

Слой HTTP предельно тонкий и лишь принимает запрос, вызывает сервис и возвращает ответ или ошибку 404. Никакой бизнес-логики здесь нет, и это правильно.

Строка `Depends(get_film_service)` выполняет **внедрение зависимостей**. FastAPI сам вызовет `get_film_service`, а тот, в свою очередь, получит клиентов Redis и Elasticsearch. Обработчику не нужно знать, откуда берутся соединения, а в тестах их легко подменить заглушками. Класс `Film(BaseModel)` описывает формат ответа, а pydantic проверит типы и заодно добавит схему в автодокументацию, доступную по адресу `/api/openapi`.

## Сервисный слой

**services/film.py:**

```python
from functools import lru_cache
from typing import Optional
from aioredis import Redis
from elasticsearch import AsyncElasticsearch, NotFoundError
from fastapi import Depends

from db.elastic import get_elastic
from db.redis import get_redis
from models.film import Film

class FilmService:
    def __init__(self, redis: Redis, elastic: AsyncElasticsearch):
        self.redis = redis
        self.elastic = elastic
    
    async def get_by_id(self, film_id: str) -> Optional[Film]:
        film = await self._film_from_cache(film_id)
        if not film:
            film = await self._get_film_from_elastic(film_id)
            if not film:
                return None
            await self._put_film_to_cache(film)
        return film
    
    async def _get_film_from_elastic(self, film_id: str) -> Optional[Film]:
        try:
            doc = await self.elastic.get('movies', film_id)
        except NotFoundError:
            return None
        return Film(**doc['_source'])
    
    async def _film_from_cache(self, film_id: str) -> Optional[Film]:
        data = await self.redis.get(film_id)
        if not data:
            return None
        film = Film.parse_raw(data)
        return film
    
    async def _put_film_to_cache(self, film: Film):
        await self.redis.set(film.id, film.json(), expire=60 * 5)

@lru_cache()
def get_film_service(
    redis: Redis = Depends(get_redis),
    elastic: AsyncElasticsearch = Depends(get_elastic),
) -> FilmService:
    return FilmService(redis, elastic)
```

Здесь живёт вся логика, и её стоит прочитать внимательно. Метод `get_by_id` реализует классический шаблон **cache-aside**, где сначала заглядывают в кеш, при промахе идут в основное хранилище и кладут результат в кеш на будущее (здесь на 5 минут, `expire=60 * 5`). Приватные методы с подчёркиванием разделяют три элементарные операции, взять из Elasticsearch, взять из кеша и положить в кеш.

Декоратор `@lru_cache()` на фабрике сервиса гарантирует, что объект `FilmService` создастся один раз, а не на каждый HTTP-запрос.

## Модели

**models/film.py:**

```python
import orjson
from pydantic import BaseModel

def orjson_dumps(v, *, default):
    return orjson.dumps(v, default=default).decode()

class Film(BaseModel):
    id: str
    title: str
    description: str
    
    class Config:
        json_loads = orjson.loads
        json_dumps = orjson_dumps
```

Модель остаётся единственным описанием того, как выглядит фильм, и на неё опираются все слои сразу. Pydantic разбирает по ней ответ Elasticsearch, он же сериализует объект в кеш и обратно. Класс `Config` подменяет стандартный модуль `json` на заметно более быстрый `orjson`, поскольку на кешируемых ответах сериализация оказывается не самой дешёвой частью запроса.

Заметь, что моделей здесь две, `models.Film` с полным набором полей и `Film` из слоя API всего с двумя. Дублирования тут нет, разделение сделано сознательно. Первая описывает то, что лежит в хранилище, вторая то, что мы обещали отдавать наружу. Добавив поле в хранилище, ты не сломаешь контракт API случайным образом.

## Что здесь стоит перенять

Пример небольшой, но в нём собраны решения, окупающиеся в любом сервисе, в том числе в том, что ты напишешь для своей установки.

* **разделение на слои**, при котором API, логика и доступ к данным живут отдельно и заменяются независимо;
* **внедрение зависимостей**, когда код не создаёт свои соединения сам, а получает их извне, что заодно делает его тестируемым;
* **конфигурация через переменные окружения**, не оставляющая в исходниках ни одного адреса или пароля;
* **кеширование**, самый дешёвый способ ускорить сервис, если данные меняются редко, а запрашиваются часто;
* **версионирование API**, где `/api/v1/` появляется с первого дня, чтобы потом не ломать существующих клиентов;
* **асинхронность**, дающая при работе с сетью и базами выигрыш почти бесплатно.

Запускается всё в контейнерах, где Dockerfile для приложения соседствует с образами Redis и Elasticsearch, связанными через Docker Compose. Как это устроено, мы разбирали в главе про [Docker](../dev/docker.md).
