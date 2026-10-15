import random
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

# =========================================================
# Конфигурация
# =========================================================

random.seed(1)
np.random.seed(1)

N_DAYS = 7*10 # Сколько дней от START_DATE просимулировать
START_DATE = datetime(2026, 10, 12) - timedelta(weeks=N_DAYS/7)

APP_RELEASE = START_DATE - timedelta(weeks=N_DAYS/7)
N_USERS = 2_000 # Общее кол-во уникальных пользователей за весь период жизни приложения

EVENT_TYPES = {
	'enters_app':  [0.00, 0.80, 0.15, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.05], # входит в приложение
    'browse':      [0.00, 0.30, 0.10, 0.40, 0.00, 0.00, 0.10, 0.05, 0.00, 0.05], # листает главную / каталог
    'search':      [0.00, 0.20, 0.15, 0.50, 0.00, 0.00, 0.05, 0.05, 0.00, 0.05], # вводит запрос
    'play':        [0.00, 0.00, 0.00, 0.00, 0.30, 0.65, 0.00, 0.00, 0.00, 0.05], # запускает контент
	'seek':        [0.00, 0.00, 0.00, 0.00, 0.65, 0.15, 0.00, 0.00, 0.15, 0.05], # перемотка назад / вперед
    'pause':       [0.00, 0.10, 0.00, 0.75, 0.10, 0.00, 0.00, 0.00, 0.00, 0.05], # ставит на паузу
    'add_to_list': [0.00, 0.90, 0.00, 0.05, 0.00, 0.00, 0.00, 0.00, 0.00, 0.05], # добавляет в «посмотреть позже»
    'rate':        [0.00, 0.50, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.50], # оценивает контент
    'finish':      [0.00, 0.45, 0.00, 0.00, 0.00, 0.00, 0.00, 0.50, 0.00, 0.05], # досмотрел до конца
	'exits_app':   [1.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00, 0.00], # закрывает приложение
}

EVENT_RATE = 0.5 # Среднее кол-во событий в минуту
SESSION_RATE = 1 # Среднее кол-во сессий в день

DAILY_ACTIVITY_BASE = 0.5 # Базовая вероятность, что сегодня пользователь зайдет в приложение. Определяет DAU

WEEKDAY_FACTOR = [0.9, 0.95, 1.0, 1.0, 1.15, 1.3, 1.25] # День недели: пн..вс

DAY_PEAK = 4 # день, на который будет пик вовлечённости
E_MIN = 0.5 # Мин уровень вовлечённости
E_MAX = 2 # Макс уровень вовлечённости

CHURN_BASE = 0.01 # риск ухода в нулевой день
CHURN_COOLDOWN = 21 # день, после которого риск перестанет расти

DEVICES = {
	'tv':     [0.8, 0.1, 0.1],
	'web':    [0.1, 0.8, 0.1],
	'mobile': [0.1, 0.1, 0.8]
}
DEVICES_RATIO = {
	'tv': 0.4,
	'web': 0.25,
	'mobile': 0.35
}

# =========================================================
# Проверка конфигурации
# =========================================================

if not isinstance(START_DATE, datetime) or not isinstance(APP_RELEASE, datetime):
	raise ValueError('START_DATE и APP_RELEASE должны быть в формате datetime. Также убедитесь, что это не формат date, а именно datetime')

if START_DATE < APP_RELEASE:
	raise ValueError('Старт симуляции START_DATE не может быть раньше даты релиза приложения APP_RELEASE')

if N_DAYS <= 0 or N_DAYS % 1 > 0:
	raise ValueError('N_DAYS должно быть целым и больше нуля')

if N_USERS <= 0 or N_USERS % 1 > 0:
	raise ValueError('N_USERS должно быть целым и больше нуля')

if EVENT_RATE <= 0:
	raise ValueError('EVENT_RATE должно быть больше нуля')

if SESSION_RATE <= 0:
	raise ValueError('SESSION_RATE должно быть больше нуля')

if DAILY_ACTIVITY_BASE <= 0 or DAILY_ACTIVITY_BASE > 1:
	raise ValueError('DAILY_ACTIVITY_BASE должно быть больше нуля и меньше единицы')

if DAY_PEAK <= 0 or DAY_PEAK % 1 > 0:
	raise ValueError('DAY_PEAK должно быть целым и больше нуля')

if E_MIN <= 0:
	raise ValueError('E_MIN должно быть больше нуля')

if E_MAX <= 0:
	raise ValueError('E_MAX должно быть больше нуля')

if CHURN_BASE <= 0:
	raise ValueError('CHURN_BASE должно быть больше нуля')

if CHURN_COOLDOWN <= 0 or CHURN_COOLDOWN % 1 > 0:
	raise ValueError('CHURN_COOLDOWN должно быть целым и больше нуля')

# =========================================================
# Генератор
# =========================================================

# https://www.desmos.com/calculator/qynr7agg8s
def get_churn_day():
	p = random.random() # [0, 1)
	x = -np.log(1 - p) / (CHURN_BASE * CHURN_COOLDOWN)
	if x >= 1: # для np.log(1 - x) должно быть x < 1
		return float("inf")
	return -CHURN_COOLDOWN * np.log(1 - x)

# https://www.desmos.com/calculator/qo0atj8cki
# Чтобы не было ситуации retention D1 ≈ D7 ≈ D30
def engagement_factor(days_since):
    return E_MIN + (E_MAX - E_MIN) * days_since / DAY_PEAK * np.exp(1 - days_since / DAY_PEAK)

def get_random_first_day():
	# Случайный день между датой релиза приложения и датой конца симуляции
	sim_end_date = START_DATE + timedelta(days=N_DAYS)
	d = (sim_end_date - APP_RELEASE).days
	offset = timedelta(days=random.randint(0, d))
	return APP_RELEASE + offset

def next_state(current_state, matrix):
	return str(np.random.choice(list(matrix.keys()), p=matrix[current_state]))

def generate_day_events(user_id, wakeup_time, fall_asleep_time):
	events_rows = []
	t = wakeup_time
	# Между переходами всегда есть временной промежуток
	# Если пользователь вышел из приложения, то промежуток вероятнее будет больше
	# SESSION_RATE это среднее кол-во сессий в день бодрствования
	# нам нужно получить среднее кол-во сессий на минуту бодрствования,
	# так как минута это единица времени в нашем пуассонвском процессе
	wakefulness_min = (fall_asleep_time - wakeup_time).seconds / 60
	session_rate_min = SESSION_RATE / wakefulness_min
	# Временной промежуток между пробуждением и первым заходом в приложение
	t += timedelta(minutes=random.expovariate(session_rate_min))
	# Первое событие это всегда заход в приложение
	markov_state = 'enters_app'
	content_id = None
	# Первое устройство выберем случайно
	device_list = list(DEVICES_RATIO.keys())
	device_ratio = list(DEVICES_RATIO.values())
	device_state = str(np.random.choice(device_list, p=device_ratio))
	# До тех пор пока не уснет
	while t < fall_asleep_time:
		# Фиксируем текущее состояние
		events_rows.append({
			'user_id': user_id,
			'event_date': t.strftime('%Y-%m-%d %H:%M:%S'),
			'event_type': markov_state,
			'device': device_state,
			'content_id': content_id
		})
		# Временной промежуток между переходами
		lam = session_rate_min if markov_state == 'exits_app' else EVENT_RATE
		t += timedelta(minutes=random.expovariate(lam))
		# Если пользователь закрыл приложение, то, возможно, сменит устройство
		if markov_state == 'exits_app':
			device_state = next_state(device_state, DEVICES)
		# Переходим в следующее состояние
		markov_state = next_state(markov_state, EVENT_TYPES)
		# Если он перешел в состояние с контентом, то content_id должен быть заполнен до фиксации
		if markov_state in ['play', 'add_to_list']:
			content_id = random.randint(1,10_000)
		# Если это не другие состояния с контентом, то его надо обнулить
		# в ином случае не трогать уже сгенерированный
		elif markov_state not in ['seek', 'pause', 'finish', 'rate']:
			content_id = None
	# Есть ненулевая вероятность, что цикл закончится, не на 'exits_app'
	# Однако эта вероятность маленькая, так как вероятность конца цикла в перерывах между сессиями выше
	# Поэтому ради простоты кода оставим это - пусть будет естественным шумом
	return events_rows

def generate_user(i):
	user_rows = []
	# Личный уровень активности пользователя
	propensity = max(0.1, random.gauss(1.0, 0.3))
	first_day_date = get_random_first_day()
	# День, когда перестанет открывать приложения
	churn_day = get_churn_day()
	# Первый день пользователя может быть сильно позже START_DATE, но не раньше
	sim_start_date = max(START_DATE, first_day_date)
	sim_end_date = START_DATE + timedelta(days=N_DAYS)
	sim_days = (sim_end_date - sim_start_date).days
	# Если 00:00 это начало временной линии, то нам надо получить число часов ~ N(0, 3),
	# которое мы прибавим к 00:00 и получим во сколько пользователь уснул вчера
	fall_asleep_delta = timedelta(hours=random.gauss(0, 2))
	for d_i in range(sim_days):
		# Устанавливаем текущую дату
		t_day = sim_start_date + timedelta(days=d_i)
		# Свойства пользователя на сегодня
		weekday_factor = WEEKDAY_FACTOR[t_day.weekday()]
		days_in_app = (t_day - first_day_date).days
		engagement = engagement_factor(days_in_app)
		# Перестанет ли заходить?
		if days_in_app >= churn_day:
			break
		# Зайдет ли сегодня в приложение?
		p_active = DAILY_ACTIVITY_BASE * engagement * propensity * weekday_factor
		p_active = min(max(p_active, 0.0), 1.0) # ограничивает результат между 0 и 1
		if p_active < random.random():
			continue
		# Раз он решил зайти...
		# Сколько пользователь спал часов сегодня ночью ~ N(8, 1)
		sleep_time = timedelta(hours=random.gauss(8, 1))
		# Чтобы t_day не показывала вчерашний или завтрашний день из-за экстремальных значений
		sleep_delta = fall_asleep_delta + sleep_time
		# Минимальный час пробуждения в 00:00
		sleep_delta = max(timedelta(hours=0), sleep_delta)
		# Максимальный час пробуждения в 17:00
		sleep_delta = min(timedelta(hours=17), sleep_delta)
		# Мы получили время во сколько пользователь проснулся
		wakeup_datetime = t_day + sleep_delta
		# Заранее посчитаем во сколько пользователь сегодня уснет
		# Предположим, что он бодрствует в среднем 24-8 = 16 часов
		wakefulness_delta = timedelta(hours=random.gauss(16, 1))
		fall_asleep_datetime = wakeup_datetime + wakefulness_delta
		# Генерируем события за день
		user_rows.extend(generate_day_events(i, wakeup_datetime, fall_asleep_datetime))
	return user_rows

table = []

for i in range(N_USERS):
	table.extend(generate_user(i))

df = pd.DataFrame(table)
print(df.head(10))
print("Всего событий:", len(df))
df.to_csv('events.csv', index=False)