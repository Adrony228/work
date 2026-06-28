# Вступительный экзамен — Проектирование, разработка и управление сложными информационными системами

АНОО ВО «Университет «Сириус»» · Письменный экзамен · 180 минут

## Структура экзамена

| Задание | Баллы | Где выполнять |
|---------|-------|---------------|
| 1 — арифметика | 10 | бумага |
| 2 — неравенство | 10 | бумага |
| 3 — геометрия | 15 | бумага |
| 4 — текстовая задача | 15 | бумага |
| 5 — системы счисления | 10 | бумага |
| 6 — поиск ошибок в коде | 10 | бумага |
| 7 — принадлежность точки области | 15 | компьютер (Python) |
| 8 — программа для исполнителя «Сириус» | 15 | компьютер / бумага |

**Итого:** 100 баллов.

---

## Варианты

| Вариант | С ответами | Бланк для печати |
|---------|------------|------------------|
| 2 | [variant-2.md](variant-2.md) | [variant-2-blank.html](variant-2-blank.html) |
| 3 | [variant-3.md](variant-3.md) | [variant-3-blank.html](variant-3-blank.html) |
| 4 | [variant-4.md](variant-4.md) | [variant-4-blank.html](variant-4-blank.html) |
| 5 | [variant-5.md](variant-5.md) | [variant-5-blank.html](variant-5-blank.html) |
| 6 | [variant-6.md](variant-6.md) | [variant-6-blank.html](variant-6-blank.html) |
| 7 | [variant-7.md](variant-7.md) | [variant-7-blank.html](variant-7-blank.html) |
| 8 | [variant-8.md](variant-8.md) | [variant-8-blank.html](variant-8-blank.html) |
| 9 | [variant-9.md](variant-9.md) | [variant-9-blank.html](variant-9-blank.html) |
| 10 | [variant-10.md](variant-10.md) | [variant-10-blank.html](variant-10-blank.html) |
| 11 | [variant-11.md](variant-11.md) | [variant-11-blank.html](variant-11-blank.html) |
| 12 | [variant-12.md](variant-12.md) | [variant-12-blank.html](variant-12-blank.html) |
| 13 | [variant-13.md](variant-13.md) | [variant-13-blank.html](variant-13-blank.html) |
| 14 | [variant-14.md](variant-14.md) | [variant-14-blank.html](variant-14-blank.html) |
| 15 | [variant-15.md](variant-15.md) | [variant-15-blank.html](variant-15-blank.html) |
| 16 | [variant-16.md](variant-16.md) | [variant-16-blank.html](variant-16-blank.html) |

**Ключ ответов (варианты 5–16):** [answers-key-5-16.md](answers-key-5-16.md)

---

## Как печатать бланк

1. Откройте файл `variant-N-blank.html` в браузере (Chrome / Firefox).
2. Нажмите **Ctrl+P** (или **Cmd+P** на macOS).
3. Параметры:
   - формат **A4**;
   - масштаб **100%**;
   - поля — по умолчанию;
   - включите **«Фоновая графика»** (для сетки и закрашенной области на рисунке задания 7).
4. Бланк занимает **3 страницы**.

---

## Задание 7 — графики

В вариантах 5–16 рисунок задания 7 содержит:

- координатную сетку с подписями осей;
- три цветные кривые с легендой;
- чётко выделенную закрашенную область;
- подпись «Рис. б».

---

## Задание 8 — исполнитель «Сириус»

Во всех вариантах 5–16 используется **массив памяти** `w[0]…w[9]` для промежуточных значений (стек не применяется). Чередуются:

- **метод половинного деления** для корня кубического уравнения;
- **метод Ньютона** для корня кубического уравнения.

---

## Генерация новых вариантов

```bash
python3 tools/generate_variants.py
```

Скрипт пересоздаёт файлы `variant-5.md` … `variant-16.md` и соответствующие HTML-бланки.
