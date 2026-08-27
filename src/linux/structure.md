# Внутреннее устройство Linux

## Введение

### Почему важно изучать внутреннее устройство Linux

**Linux** доминирует в современных IT-инфраструктурах:
- 90% облачных инстансов работают на Linux
- Все суперкомпьютеры из топ-500 используют Linux
- Android (на базе Linux) - самая популярная мобильная ОС
- Встроенные системы и IoT устройства в основном на Linux

**Понимание внутренних механизмов** позволяет:
- **Диагностировать сложные проблемы** - от зависаний до утечек памяти
- **Оптимизировать производительность** - понимать, куда смотреть при нагрузке
- **Писать эффективный код** - знать стоимость системных вызовов
- **Эффективно использовать облака** - понимать, что происходит "под капотом"

**Ключевой принцип**: "Облака — это просто компьютеры в другом месте". Все те же процессы, память, сеть, но в удаленном дата-центре.

---

## 1. Зачем изучать Linux?

### Практическая ценность глубоких знаний

#### Быстрая диагностика проблем
```bash
# Вместо случайного тыкания
strace -p <pid>                    # что делает процесс?
perf record -g <command>          # где тратится время?
cat /proc/<pid>/status            # в каком состоянии?
```

**Пример из практики**: Сервис периодически "зависал". 
Анализ показал, что процесс переходил в состояние `D` (Uninterruptible sleep) при работе с NFS. 
Решение: настройка таймаутов и retry-логики.

#### Эффективное программирование
Знание стоимости операций:
- Системный вызов: ~1000 циклов CPU
- Context switch: ~1000-10000 циклов
- Page fault: ~10-100 микросекунд

**Оптимизация**: Сведение системных вызовов к минимуму, использование буферизации.

#### Облачные технологии
Контейнеры, оркестрация, serverless - все построено на механизмах Linux:
- **Docker** → cgroups + namespaces
- **Kubernetes** → управление процессами в масштабе
- **AWS Lambda** → изоляция и быстрый запуск

---

## 2. Процессы

### Детальное понимание процессов

#### Что такое процесс на самом деле?

Процесс - это не просто "запущенная программа", это **контейнер выполнения** с:

**Ресурсы**:
- Виртуальное адресное пространство
- Открытые файловые дескрипторы
- Учетные данные и привилегии
- Сигнальные маски и обработчики

**Метаданные**:
- PID, PPID, UID, GID
- Приоритеты планирования
- Состояние выполнения
- Потребление ресурсов

#### Структура процесса в ядре

```c
// Упрощенная task_struct (include/linux/sched.h)
struct task_struct {
    volatile long state;                    // состояние процесса
    void *stack;                           // указатель на стек
    struct mm_struct *mm;                  // память процесса
    struct files_struct *files;            // открытые файлы
    struct signal_struct *signal;          // сигналы
    // ... сотни полей
};
```

**Практическое использование**:
```bash
# Анализ конкретного процесса
ls -la /proc/1234/
cat /proc/1234/maps    # память процесса
cat /proc/1234/status  # состояние и лимиты
ls /proc/1234/fd/      # открытые файлы
```

### Создание процессов: fork() и exec()

#### Механизм Copy-on-Write (CoW)

**До оптимизации**:
- `fork()` копировал всю память родителя
- Очень дорогая операция для больших процессов

**После CoW**:
- Страницы памяти помечаются как read-only
- Реальная копия происходит только при записи
- Экономия памяти и времени

```c
pid_t pid = fork();
if (pid == 0) {
    // Дочерний процесс
    // Страницы памяти разделяются до первой записи
    execve("/bin/ls", args, env);
} else {
    // Родительский процесс
    waitpid(pid, &status, 0);
}
```

### Потоки (Threads) vs Процессы

#### Архитектурные различия

| Аспект | Процесс | Поток |
|--------|---------|-------|
| Память | Изолированная | Разделяемая |
| Файлы | Отдельные таблицы | Общая таблица |
| Стоимость создания | Высокая | Низкая |
| Изоляция | Полная | Минимальная |

#### Практические сценарии использования

**Используем процессы когда**:
- Нужна изоляция отказоустойчивости
- Работа с разными security-контекстами
- Масштабирование на несколько машин

**Используем потоки когда**:
- Разделение состояния (кеш, соединения)
- Низкая задержка взаимодействия
- Эффективное использование CPU кеша

### Межпроцессное взаимодействие (IPC)

#### Сигналы - асинхронные уведомления

```c
// Отправка сигнала
kill(pid, SIGTERM);

// Обработка сигнала
void handler(int sig) {
    // Асинхронно! Осторожно с shared state
}
signal(SIGTERM, handler);
```

**Важно**: Большинство функций не являются signal-safe! Используй только async-signal-safe функции в обработчиках.

#### Pipes - однонаправленная коммуникация

```bash
# Неименованные каналы
ls -la | grep ".txt" | wc -l

# Именованные каналы (FIFO)
mkfifo mypipe
echo "data" > mypipe &
cat mypipe
```

**Особенности**:
- Буферизация на уровне ядра
- Blocking I/O по умолчанию
- Размер буфера можно настраивать

#### Разделяемая память - максимальная производительность

```c
// Создание shared memory
int shm_id = shmget(key, size, IPC_CREAT | 0666);
void *ptr = shmat(shm_id, NULL, 0);

// Использование
memcpy(ptr, data, data_size);
```

**Преимущества**:
- Нет копирования данных
- Минимальная задержка
- Прямой доступ к памяти

**Недостатки**:
- Сложная синхронизация
- Риск состояния гонки

#### Семафоры - координация доступа

```c
// Бинарный семафор (мьютекс)
sem_wait(&mutex);
// Критическая секция
sem_post(&mutex);
```

**Типы семафоров**:
- **Binary** (0 или 1) - для взаимного исключения
- **Counting** - для ограничения ресурсов

### Состояния процессов: полный цикл жизни

#### Детали каждого состояния

**R (Running/Runnable)**:
- Процесс готов к выполнению или выполняется
- Находится в runqueue планировщика
- Может быть ограничен только доступностью CPU

**S (Interruptible Sleep)**:
- Ожидание события (I/O, семафор, сигнал)
- Может быть прерван сигналом
- Типичное состояние для I/O bound процессов

**D (Uninterruptible Sleep)**:
- Ожидание аппаратного I/O (диск, сеть)
- **Не может быть прерван даже kill -9**
- Опасное состояние - может привести к hung process

**T (Stopped)**:
- Приостановлен сигналом (SIGSTOP, SIGTSTP)
- Может быть продолжен (SIGCONT)
- Используется дебаггерами

**Z (Zombie)**:
- Процесс завершен, но родитель не забрал статус
- Ресурсы освобождены, осталась только запись в таблице процессов
- **Лечение**: завершить родительский процесс

#### Практический мониторинг

```bash
# Понимание состояния процессов
ps aux | awk '{print $8}' | sort | uniq -c

# Поиск проблемных процессов
# Процессы в D состоянии
ps aux | awk '$8=="D" {print $0}'

# Zombie процессы
ps aux | awk '$8=="Z" {print $0}'
```

---

## 3. Планировщик (Scheduler)

### Эволюция планировщиков Linux

#### O(N) планировщик (до 2.4)
```c
// Псевдокод старого планировщика
for (each task in system) {
    calculate_goodness(task);
    if (goodness > max_goodness) {
        next_task = task;
        max_goodness = goodness;
    }
}
```
**Проблемы**: O(N) сложность, не масштабировался на многоядерные системы

#### O(1) планировщик (2.6.0 - 2.6.22)
- Две очереди: active и expired
- Bitmap для быстрого поиска
- Константное время планирования

**Достижения**: Хорошая масштабируемость, поддержка SMP

#### CFS (Completely Fair Scheduler) (2.6.23+)
```c
// Основан на красно-черных деревьях
struct rb_root_cached {
    struct rb_root rb_root;
    struct rb_node *rb_leftmost;
};
```

**Философия**: "Справедливое" распределение CPU времени

### Приоритеты и политики планирования

#### Real-Time политики

**SCHED_FIFO (First-In-First-Out)**:
- Бесконечный time slice
- Вытесняется только более приоритетным RT процессом
- **Опасность**: может занять CPU навсегда

**SCHED_RR (Round Robin)**:
- Фиксированный time slice (100ms по умолчанию)
- Циклическое переключение между процессами одинакового приоритета
- Более безопасен чем FIFO

#### Normal политики

**SCHED_NORMAL/OTHER**:
- Динамические приоритеты (nice значения)
- Интерактивные процессы получают "бонус"
- Фоновые процессы слегка "штрафуются"

#### Nice значения и приоритеты

```bash
# Установка nice значения
nice -n 10 ./long_running_task    # низкий приоритет
nice -n -20 ./critical_task       # высокий приоритет

# Изменение running процесса
renice -n 5 -p 1234
```

**Диапазон**: -20 (высший) до +19 (низший)

### CFS: внутреннее устройство

#### Ключевые концепции

**Virtual Runtime (vruntime)**:
- Время выполнения, нормализованное по приоритету
- Процессы с меньшим vruntime выполняются первыми
- Nice значения влияют на скорость накопления vruntime

**Target Latency**:
- Время, за которое все runnable процессы должны выполниться
- По умолчанию: 6ms для desktop, 24ms для server

**Minimal Granularity**:
- Минимальное время выполнения перед вытеснением
- 0.75ms для предотвращения частого переключения

#### Реализация на красно-черных деревьях

```c
// Вставка процесса в дерево
struct sched_entity {
    struct rb_node run_node;
    u64 vruntime;
    // ...
};

// Быстрый поиск процесса с минимальным vruntime
struct task_struct *pick_next_task(struct rq *rq) {
    struct rb_node *left = rb_first_cached(&rq->tasks_timeline);
    return rb_entry(left, struct task_struct, se.run_node);
}
```

**Преимущества**: O(log N) для вставки/удаления

### Управление планировщиком на практике

#### CPU Affinity

```bash
# Привязка процесса к конкретным ядрам
taskset -c 0,1 ./application

# Просмотр текущей маски
taskset -p 1234

# Запуск с распределением по ядрам
numactl --cpunodebind=0,1 --membind=0,1 ./app
```

**Сценарии использования**:
- Изоляция критичных процессов
- Улучшение locality кеша
- NUMA-оптимизация

#### Настройка планировщика

```bash
# Просмотр параметров
cat /proc/sys/kernel/sched_min_granularity_ns
cat /proc/sys/kernel/sched_latency_ns

# Изменение параметров
echo 10000000 > /proc/sys/kernel/sched_latency_ns
```

#### Мониторинг планировщика

```bash
# Статистика переключений
cat /proc/1234/sched

# Очереди выполнения
cat /proc/sched_debug

# Профилирование
perf sched record ./application
perf sched latency
```

---

## 4. Прерывания

### Архитектура прерываний в x86/x64

#### Аппаратные прерывания (IRQs)

**Источники**:
- Таймеры
- Сетевые карты
- Дисковые контроллеры
- USB устройства

**Механизм**:
```c
// Регистрация обработчика
request_irq(IRQ_NUMBER, handler, flags, name, dev);

// Обработчик прерывания
static irqreturn_t my_handler(int irq, void *dev_id) {
    // Быстрая обработка
    return IRQ_HANDLED;
}
```

#### Исключения процессора

**Типы**:
- **Faults** - исправимые (page fault)
- **Traps** - преднамеренные (breakpoints)
- **Aborts** - фатальные ошибки

### Обработка прерываний: Upper и Bottom Halves

#### Upper Half (Верхняя половина)

**Требования**:
- Максимально быстрое выполнение
- Минимальная работа
- Без блокирующих операций

```c
// Типичный upper half
irqreturn_t eth_interrupt(int irq, void *dev_id) {
    struct net_device *dev = dev_id;
    disable_irq_nosync(dev->irq);
    schedule_work(&dev->tx_work);
    return IRQ_HANDLED;
}
```

#### Bottom Half (Нижняя половина)

**Механизмы**:

1. **SoftIRQs**:
   - Статические в ядре (сеть, блокирующие устройства)
   - Очень быстрые, но сложные в использовании

2. **Tasklets**:
   - Динамические, atomic scheduling
   - Не могут выполняться параллельно

3. **Work Queues**:
   - Выполняются в контексте процесса
   - Могут sleep и использовать блокирующие вызовы

```c
// Work queue пример
DECLARE_WORK(my_work, my_work_function);

void my_work_function(struct work_struct *work) {
    // Медленная обработка
    process_packets();
    enable_irq(dev->irq);
}
```

### Практическая работа с прерываниями

#### Мониторинг прерываний

```bash
# Статистика прерываний
cat /proc/interrupts

# Распределение прерываний по CPU
cat /proc/irq/*/smp_affinity

# Изменение привязки прерываний
echo 2 > /proc/irq/24/smp_affinity
```

#### Оптимизация обработки

**Techniques**:
- Balance IRQs across CPUs
- Use MSI instead of legacy interrupts
- Tune network queue sizes
- Adjust IRQ coalescing settings

---

## 5. Системные вызовы

### Механизм системных вызовов

#### Переключение между пространствами

**Пользовательское пространство** → **Пространство ядра**:
```assembly
; x86-64 системный вызов
mov rax, 1      ; номер syscall (write)
mov rdi, 1      ; fd (stdout)
mov rsi, buffer ; буфер
mov rdx, count  ; размер
syscall         ; переход в ядро
```

**Процесс переключения**:
1. Сохранение контекста пользователя
2. Переход в режим ядра
3. Валидация параметров
4. Выполнение операции
5. Возврат результата
6. Восстановление контекста

#### Таблица системных вызовов

```c
// Определение syscall (kernel/sys.c)
SYSCALL_DEFINE3(write, unsigned int, fd, const char __user *, buf,
                size_t, count)
{
    struct fd f = fdget_pos(fd);
    // ... обработка
    return ret;
}
```

**Важно**: Все параметры проверяются на валидность!

### Безопасность системных вызовов

#### Проверки доступа

```c
// Проверка указателей из userspace
if (copy_from_user(kernel_buf, user_buf, size))
    return -EFAULT;

// Проверка прав доступа
if (!file_permission(file, MAY_READ))
    return -EPERM;
```

#### Capabilities-based security

```c
// Вместо проверки UID == 0
if (!capable(CAP_SYS_ADMIN))
    return -EPERM;
```

### Производительность системных вызовов

#### Измерение стоимости

```c
#include <sys/time.h>

struct timeval start, end;
gettimeofday(&start, NULL);
// системный вызов
gettimeofday(&end, NULL);

long microseconds = (end.tv_sec - start.tv_sec) * 1000000 
                  + (end.tv_usec - start.tv_usec);
```

**Типичные затраты**:
- Простой syscall: 0.1 - 1 микросекунда
- I/O syscalls: 1 - 1000 микросекунд
- Context switch: 1 - 10 микросекунд

#### Оптимизация

**Методы**:
- Batch operations (writev вместо множества write)
- Memory mapping (mmap вместо read/write)
- Avoid unnecessary syscalls
- Use vDSO для частых вызовов (gettimeofday)

---

## 6. Память процесса

### Виртуальная память: полная картина

#### Макет адресного пространства

```
0x0000000000000000 ┌─────────────────┐
                   │    Зарезервировано   │
                   │   (NULL-ptr guard)  │
0x0000000000400000 ├─────────────────┤
                   │       Text        │
                   │  (код программы)  │
0x0000000000600000 ├─────────────────┤
                   │     Data (init)    │
                   │ (инициализированные)│
0x0000000000601000 ├─────────────────┤
                   │    BSS (uninit)    │
                   │ (неинициализированные)│
0x0000000000800000 ├─────────────────┤
                   │        Heap        │
                   │   (динамическая)   │
                   │        ↓           │
0x00007ffff0000000 ├─────────────────┤
                   │     MMAP region    │
                   │   (библиотеки,     │
                   │    shared mem)     │
0x00007ffff7a00000 ├─────────────────┤
                   │       Stack        │
                   │   (автоматические) │
                   │        ↑           │
0x00007ffffff00000 ├─────────────────┤
                   │   Kernel space     │
                   │  (недоступно)      │
0xffffffffffffffff └─────────────────┘
```

### Управление памятью на практике

#### Анализ памяти процесса

```bash
# Детальная информация о памяти
pmap -XX 1234

# Статистика памяти
cat /proc/1234/smaps

# Page faults
ps -o min_flt,maj_flt,cmd -p 1234
```

#### Типы page faults

**Minor Fault**:
- Страница в физической памяти
- Но не отображена в page tables процесса
- Быстрое разрешение

**Major Fault**:
- Страница не в физической памяти
- Требуется загрузка с диска
- Медленное разрешение

### Проблемы с памятью и решения

#### Out of Memory (OOM)

**Механизм OOM killer**:
1. Ядро обнаруживает нехватку памяти
2. Вычисляет "badness score" для каждого процесса
3. Выбирает и завершает процесс с максимальным score

**Управление OOM**:
```bash
# Настройка политики OOM
echo -1000 > /proc/1234/oom_score_adj    # защитить процесс
echo 1000 > /proc/1234/oom_score_adj     # первым кандидат

# Ручной вызов OOM killer
echo f > /proc/sysrq-trigger
```

#### SWAP управление

```bash
# Мониторинг swap
swapon --show
free -h

# Настройка swappiness
echo 10 > /proc/sys/vm/swappiness    # меньше swap (сервер)
echo 60 > /proc/sys/vm/swappiness    # больше swap (десктоп)
```

#### NUMA оптимизация

```bash
# Информация о NUMA
numactl --hardware

# Запуск с учетом NUMA
numactl --membind=0 --cpunodebind=0 ./application

# Статистика NUMA
cat /proc/1234/numa_maps
```

---

## 7. Изоляция

### Эволюция изоляции в Linux

#### От chroot до контейнеров

**Историческое развитие**:
- 1979: chroot в UNIX
- 2000: FreeBSD Jails
- 2001: Linux-VServer
- 2004: Solaris Zones
- 2008: LXC (Linux Containers)
- 2013: Docker
- 2014: Kubernetes

### Cgroups: управление ресурсами

#### Иерархия cgroups v2

```
/sys/fs/cgroup/
├── system.slice/          # системные службы
│   ├── ssh.service
│   └── docker.service
├── user.slice/            # пользовательские процессы
│   ├── user-1000.slice
│   └── user-1001.slice
├── kubepods.slice/        # Kubernetes pods
│   ├── pod1/
│   └── pod2/
└── cgroup.controllers     # доступные контроллеры
```

#### Контроллеры ресурсов

**CPU**:
```bash
# Ограничение CPU
echo "200000 1000000" > /sys/fs/cgroup/mygroup/cpu.max
# 200ms из каждых 1000ms

# CPU shares
echo 512 > /sys/fs/cgroup/mygroup/cpu.weight
```

**Память**:
```bash
# Лимит памяти
echo 1G > /sys/fs/cgroup/mygroup/memory.max

# SWAP лимит
echo 2G > /sys/fs/cgroup/mygroup/memory.swap.max

# OOM политика
echo "oom_group" > /sys/fs/cgroup/mygroup/memory.oom.group
```

**I/O**:
```bash
# Ограничение дискового I/O
echo "8:0 rbps=1048576 wbps=1048576" > /sys/fs/cgroup/mygroup/io.max
```

### Namespaces: изоляция представлений

#### Типы namespaces

| Namespace | Изолирует | Команда |
|-----------|-----------|---------|
| PID | Process IDs | unshare --pid |
| Network | Network stack | unshare --net |
| Mount | Filesystem mounts | unshare --mount |
| UTS | Hostname, domain | unshare --uts |
| IPC | System V IPC | unshare --ipc |
| User | User/group IDs | unshare --user |
| Cgroup | Cgroup hierarchy | unshare --cgroup |
| Time | System time | unshare --time |

#### Практическое использование namespaces

**Создание изолированного окружения**:
```bash
# Создание namespace и запуск процесса
sudo unshare --fork --pid --mount-proc bash

# В новом namespace:
ps aux    # видит только свои процессы
mount     # видит только свои mount points
```

**Docker-подобный контейнер вручную**:
```bash
# Создание root filesystem
mkdir /mycontainer
debootstrap stable /mycontainer

# Запуск в изоляции
unshare --fork --pid --mount-proc --net --uts chroot /mycontainer /bin/bash

# В контейнере:
hostname mycontainer
ip link set lo up
```

## Заключение

Понимание внутреннего устройства Linux - это не академическое знание, а практический инструмент для создания надежных, производительных и безопасных систем.