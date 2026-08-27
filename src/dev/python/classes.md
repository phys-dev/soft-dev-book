# Классы в Python

## Введение

Классы в Python предоставляют средства для объектно-ориентированного программирования. В отличие от языков вроде Java и C++, Python использует явную передачу ссылки на экземпляр через параметр `self`.

**💡 Интересный факт:** Python был одним из первых языков, где объектно-ориентированность была заложена в основу дизайна с самого начала. В отличие от C++, где ООП добавлялось постепенно, или Java, где всё должно быть в классах, Python находит баланс между процедурным и объектно-ориентированным подходами.

## Базовые понятия

### Определение класса

```python
class Counter:
    """I count. That is all."""
    
    def __init__(self, initial=0):  # конструктор
        self.value = initial        # запись атрибута

    def increment(self):
        self.value += 1

    def get(self):
        return self.value          # чтение атрибута

# Использование
c = Counter(42)
c.increment()
print(c.get())  # 43
```

**💡 Интересный факт:** Название `__init__` может вводить в заблуждение — это не конструктор в традиционном понимании. Настоящий конструктор — это метод `__new__`, который создаёт объект, а `__init__` лишь инициализирует уже созданный объект. Это различие важно при наследовании от неизменяемых типов.

### Специфика Python

- Первый аргумент методов — всегда `self` (явная передача экземпляра)
- Нет модификаторов доступа, но есть соглашения об именовании:
  - `public_attribute` — публичный атрибут
  - `_internal_attribute` — внутренний атрибут (одиночное подчеркивание)
  - `__private_attribute` — приватный атрибут (двойное подчеркивание, реализуется через name mangling)

**💡 Интересный факт:** Соглашение об именовании с подчеркиваниями — это пример "соглашения между джентльменами" в Python. Технически ты всё равно можешь получить доступ к "приватным" атрибутам, но так делать не рекомендуется. Name mangling преобразует `__private` в `_ClassName__private`, что помогает избежать конфликтов имён в подклассах.

## Атрибуты классов и экземпляров

### Атрибуты экземпляра

Добавляются через присваивание к `self`:

```python
class Noop:
    def __init__(self):
        self.some_attribute = 42

noop = Noop()
noop.other_attribute = 100500  # динамическое добавление
```

**💡 Интересный факт:** Python позволяет динамически добавлять атрибуты к уже созданным объектам благодаря тому, что атрибуты хранятся в обычном словаре `__dict__`. Это даёт большую гибкость, но может приводить к трудноуловимым багам, если ты опечатаешься в имени атрибута.

### Атрибуты класса

```python
class Counter:
    all_counters = []  # атрибут класса
    
    def __init__(self, initial=0):
        Counter.all_counters.append(self)
        self.value = initial

# Также можно добавлять атрибуты после определения
Counter.some_other_attribute = 42
```

**💡 Интересный факт:** Атрибуты класса разделяются между всеми экземплярами. Это может быть как полезным (для шаблона "Моносостояние"), так и опасным — если ты изменишь изменяемый атрибут класса, это повлияет на все экземпляры!

### Словарь атрибутов

```python
noop = Noop()
noop.some_attribute = 42
print(noop.__dict__)  # {'some_attribute': 42}
print(vars(noop))     # альтернативный способ

# Динамическое управление атрибутами
noop.__dict__["dynamic_attr"] = "value"
```

**💡 Интересный факт:** Функция `vars()` без аргументов возвращает `__dict__` текущего локального пространства имён, а с одним аргументом - `__dict__` этого объекта. Это один из многих примеров того, как Python делает внутренние механизмы доступными для программиста.

### `__slots__` для оптимизации

```python
class Noop:
    __slots__ = ["some_attribute"]  # фиксирует набор атрибутов
    
    def __init__(self):
        self.some_attribute = 42

# Экономит память, но запрещает добавление новых атрибутов
```

**💡 Интересный факт:** Использование `__slots__` может сократить потребление памяти на 40-50% для объектов с небольшим количеством атрибутов, поскольку исключает необходимость в словаре `__dict__`. Однако это ограничивает гибкость и делает невозможным использование некоторых возможностей, таких как weak references, без явного указания.

## Методы

### Связанные и несвязанные методы

```python
class SomeClass:
    def do_something(self):
        print("Doing something.")

# Несвязанный метод
method = SomeClass.do_something
instance = SomeClass()
method(instance)  # нужно явно передать экземпляр

# Связанный метод
bound_method = instance.do_something
bound_method()  # self уже привязан
```

**💡 Интересный факт:** В Python 2 методы были отдельным типом (unbound method), который проверял тип первого аргумента. В Python 3 несвязанный метод — это просто функция, что делает приведенный выше код работоспособным. Это изменение упростило многие сценарии метапрограммирования.

## Свойства (Properties)

Свойства позволяют контролировать доступ к атрибутам:

```python
class BigDataModel:
    def __init__(self):
        self._params = []
    
    @property
    def params(self):
        return self._params
    
    @params.setter
    def params(self, new_params):
        assert all(p > 0 for p in new_params)
        self._params = new_params
    
    @params.deleter
    def params(self):
        del self._params

model = BigDataModel()
model.params = [0.1, 0.5, 0.4]
print(model.params)  # [0.1, 0.5, 0.4]
```

**💡 Интересный факт:** Свойства — это пример паттерна "Uniform Access Principle", который позволяет заменить поле на метод без изменения клиентского кода. В Python это реализовано через дескрипторы, что делает свойства гораздо более мощными, чем аналогичные механизмы в других языках.

## Наследование

### Базовое наследование

```python
class Counter:
    def __init__(self, initial=0):
        self.value = initial

class OtherCounter(Counter):
    def get(self):
        return self.value

oc = OtherCounter()  # вызывает Counter.__init__
print(oc.get())      # вызывает OtherCounter.get
```

**💡 Интересный факт:** Python поддерживает множественное наследование, что редко встречается в других языках. Хотя это мощная возможность, она может приводить к сложностям с порядком разрешения методов (MRO).

### Перегрузка методов и `super()`

```python
class Counter:
    all_counters = []
    
    def __init__(self, initial=0):
        self.__class__.all_counters.append(self)
        self.value = initial

class OtherCounter(Counter):
    def __init__(self, initial=0):
        self.initial = initial
        super().__init__(initial)  # вызов родительского конструктора
```

**💡 Интересный факт:** Функция `super()` в Python 3 стала значительно умнее, чем в Python 2. Она автоматически определяет нужный класс и экземпляр, что особенно важно при множественном наследовании. Под капотом она использует MRO (Method Resolution Order), вычисляемый алгоритмом C3.

### Множественное наследование

```python
class A:
    def f(self):
        print("A.f")

class B:
    def f(self):
        print("B.f")

class C(A, B):
    pass

print(C.mro())  # порядок разрешения методов
C().f()         # A.f (согласно MRO)
```

**💡 Интересный факт:** Алгоритм C3 для разрешения порядка методов был заимствован из языка Dylan. Он гарантирует, что:
1. Подклассы имеют приоритет над суперклассами
2. Порядок в списке наследования сохраняется
3. Все классы в иерархии будут посещены

### Классы-примеси

```python
class ThreadSafeMixin:
    def get_lock(self):
        # возвращает объект блокировки
        pass
    
    def increment(self):
        with self.get_lock():
            super().increment()
    
    def get(self):
        with self.get_lock():
            return super().get()

class ThreadSafeCounter(ThreadSafeMixin, Counter):
    pass
```

**💡 Интересный факт:** Примеси (mixins) — это способ реализовать композицию в мире наследования. Они широко используются в Django и других фреймворках для добавления функциональности без создания глубоких иерархий наследования. Ключевая особенность — вызов `super()`, который работает даже если следующий класс в MRO неизвестен на момент написания кода.

## Декораторы классов

```python
def singleton(cls):
    instance = None
    
    @functools.wraps(cls)
    def inner(*args, **kwargs):
        nonlocal instance
        if instance is None:
            instance = cls(*args, **kwargs)
        return instance
    
    return inner

@singleton
class Noop:
    "I do nothing at all."

print(id(Noop()) == id(Noop()))  # True
```

**💡 Интересный факт:** Декораторы классов были добавлены в Python 3.0 (PEP 3129). Они позволяют применять к классам те же техники трансформации, что и к функциям. Многие паттерны, которые раньше требовали метаклассов, теперь можно реализовать с помощью декораторов классов.

## Магические методы

### Управление атрибутами

```python
class Noop:
    def __getattr__(self, name):
        # Вызывается при доступе к несуществующему атрибуту
        return f"Attribute {name} doesn't exist"
    
    def __setattr__(self, name, value):
        # Вызывается при установке любого атрибута
        super().__setattr__(name, value)
    
    def __delattr__(self, name):
        # Вызывается при удалении атрибута
        super().__delattr__(name)

noop = Noop()
print(noop.non_existent)  # "Attribute non_existent doesn't exist"
```

**💡 Интересный факт:** Важно различать `__getattr__` и `__getattribute__`. Первый вызывается только для отсутствующих атрибутов, второй — для всех. Использование `__getattribute__` требует особой осторожности, так как неправильная реализация может привести к бесконечной рекурсии.

### Операторы сравнения

```python
import functools

@functools.total_ordering
class Counter:
    def __init__(self, value):
        self.value = value
    
    def __eq__(self, other):
        return self.value == other.value
    
    def __lt__(self, other):
        return self.value < other.value

c1, c2 = Counter(1), Counter(2)
print(c1 < c2)   # True
print(c1 >= c2)  # False (автоматически из __lt__ и __eq__)
```

**💡 Интересный факт:** Декоратор `@total_ordering` из модуля `functools` генерирует все методы сравнения на основе `__eq__` и одного из методов упорядочивания. Это пример того, как Python старается уменьшить boilerplate код, оставаясь при этом явным и понятным.

### Строковое представление

```python
class Counter:
    def __init__(self, initial=0):
        self.value = initial
    
    def __repr__(self):
        return f"Counter({self.value})"
    
    def __str__(self):
        return f"Counted to {self.value}"
    
    def __format__(self, format_spec):
        return self.value.__format__(format_spec)

c = Counter(42)
print(repr(c))           # Counter(42)
print(str(c))            # Counted to 42
print(f"{c:b}")          # 101010 (бинарное представление)
```

**💡 Интересный факт:** Соглашение в Python: `__repr__` должен быть однозначным и по возможности возвращать строку, которую можно использовать для воссоздания объекта, а `__str__` должен быть читаемым. Если `__str__` не определён, используется `__repr__`.

### Другие полезные магические методы

```python
class Identity:
    def __call__(self, x):
        # Позволяет вызывать экземпляры как функции
        return x
    
    def __bool__(self):
        # Определяет поведение в булевом контексте
        return True
    
    def __hash__(self):
        # Используется для хеширования в словарях и множествах
        return hash(id(self))

identity = Identity()
print(identity(42))  # 42
```

**💡 Интересный факт:** Метод `__call__` делает объекты вызываемыми, что является основой для создания декораторов на основе классов. Это демонстрирует философию Python, где функции и объекты не так сильно различаются — всё является объектами, а некоторые объекты можно вызывать.

## Дескрипторы

Дескрипторы позволяют переиспользовать логику свойств:

### Базовый дескриптор

```python
class NonNegative:
    def __get__(self, instance, owner):
        # magically_get_value
        pass
    
    def __set__(self, instance, value):
        assert value >= 0, "non-negative value required"
        # magically_set_value
    
    def __delete__(self, instance):
        # magically_delete_value
        pass

class VerySafe:
    x = NonNegative()
    y = NonNegative()

very_safe = VerySafe()
very_safe.x = 42      # OK
very_safe.x = -42     # AssertionError
```

**💡 Интересный факт:** Дескрипторы — это один из самых мощных, но малоизвестных механизмов Python. Функции, свойства, статические методы и методы класса — всё это реализовано через дескрипторы. Протокол дескрипторов позволяет перехватывать доступ к атрибутам на уровне класса.

### Хранение данных в дескрипторах

```python
class Proxy:
    def __init__(self, label):
        self.label = label
    
    def __get__(self, instance, owner):
        return instance.__dict__[self.label]
    
    def __set__(self, instance, value):
        instance.__dict__[self.label] = value
    
    def __delete__(self, instance):
        del instance.__dict__[self.label]

class Something:
    attr = Proxy("attr")

some = Something()
some.attr = 42
print(some.attr)  # 42
```

**💡 Интересный факт:** Хранение данных в `__dict__` экземпляра — это наиболее правильный способ реализации дескрипторов данных. Альтернативные подходы (хранение в атрибутах дескриптора или в отдельном словаре) имеют серьезные недостатки: первый нарушает работу с несколькими экземплярами, второй требует hashable объекты и может приводить к утечкам памяти.

### Встроенные дескрипторы

```python
# @property реализован через дескрипторы
class property:
    def __init__(self, get=None, set=None, delete=None):
        self._get = get
        self._set = set
        self._delete = delete
    
    def __get__(self, instance, owner):
        if self._get is None:
            raise AttributeError("unreadable attribute")
        return self._get(instance)

# @staticmethod и @classmethod тоже используют дескрипторы
class staticmethod:
    def __init__(self, method):
        self.__method = method
    
    def __get__(self, instance, owner):
        return self.__method

class classmethod:
    def __init__(self, method):
        self.__method = method
    
    def __get__(self, instance, owner):
        if owner is None:
            owner = type(instance)
        return self.__method.__get__(owner, type(owner))
```

**💡 Интересный факт:** Разница между статическими методами и методами класса именно в реализации их дескрипторов. Статический метод просто возвращает исходную функцию, а метод класса привязывается к классу. Это демонстрирует, как мощные абстракции в Python строятся из простых механизмов.

## Метаклассы

Метаклассы — это классы, экземпляры которых тоже классы.

### Базовый метакласс

```python
class Meta(type):
    def __new__(metacls, name, bases, clsdict):
        print(f"Creating class {name}")
        cls = super().__new__(metacls, name, bases, clsdict)
        return cls
    
    @classmethod
    def __prepare__(metacls, name, bases):
        # Может вернуть нестандартный mapping для clsdict
        return OrderedDict()

class Something(metaclass=Meta):
    attr = "foo"
    other_attr = "bar"
```

**💡 Интересный факт:** Метод `__prepare__` позволяет контролировать тип объекта, который используется для хранения атрибутов класса во время его создания. Это может быть использовано для сохранения порядка объявления атрибутов, добавления дополнительной валидации или логирования.

### Создание классов через `type()`

```python
# Эквивалентно class Something: attr = 42
name, bases, attrs = "Something", (), {"attr": 42}
Something = type(name, bases, attrs)

some = Something()
print(some.attr)  # 42
```

**💡 Интересный факт:** Оператор `class` в Python — это синтаксический сахар для вызова `type()` с соответствующими аргументами. Это демонстрирует консистентность Python: даже такие фундаментальные конструкции реализованы через вызовы функций.

## Модуль abc для абстрактных базовых классов

```python
import abc

class Iterable(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __iter__(self):
        pass

class Something(Iterable):
    pass

# Something()  # TypeError: Can't instantiate abstract class
```

**💡 Интересный факт:** Абстрактные базовые классы (ABC) были добавлены в Python для обеспечения более строгой проверки интерфейсов. В отличие от Java, где интерфейсы являются отдельной конструкцией, в Python они реализованы через обычные классы с метаклассом `ABCMeta`, что сохраняет согласованность языка.

## Модуль collections.abc

Полезен для создания собственных коллекций:

```python
from collections.abc import MutableMapping

class MemorizingDict(MutableMapping):
    def __init__(self, *args, **kwargs):
        self._data = dict(*args, **kwargs)
        self._history = deque(maxlen=10)
    
    def __getitem__(self, key):
        return self._data[key]
    
    def __setitem__(self, key, value):
        self._history.append(key)
        self._data[key] = value
    
    def __delitem__(self, key):
        del self._data[key]
    
    def __iter__(self):
        return iter(self._data)
    
    def __len__(self):
        return len(self._data)
    
    def get_history(self):
        return self._history
```

**💡 Интересный факт:** Модуль `collections.abc` содержит абстрактные базовые классы для встроенных типов коллекций. Наследование от этих классов гарантирует, что твоя кастомная коллекция будет совместима с ожиданиями Python и других библиотек. Например, если ты реализуешь `__getitem__` и `__len__`, то автоматически получишь поддержку `iter()` и проверку на вхождение с помощью `in`.

## Заключение

Классы в Python предоставляют мощные и гибкие средства для объектно-ориентированного программирования. От базовых концепций наследования и инкапсуляции до продвинутых возможностей вроде дескрипторов и метаклассов — Python предлагает богатый инструментарий для создания сложных и поддерживаемых программных систем.

**💡 Интересный факт:** Философия Python в отношении ООП хорошо выражена в цитате Тим Петерса (автора The Zen of Python): "ООП делает код понятным для компьютера, но не для программиста. Хороший код должен быть понятен и тому, и другому." Python находит баланс, предоставляя мощные ООП-возможности, но не заставляя их использовать там, где они не нужны.