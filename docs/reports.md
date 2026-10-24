# Raporty — wybór według danych

Obecny raport PCB HTML generowany offline zawiera widmo impedancji/S11/SWR, geometrię, stackup, metadane i opcjonalnie trzy przekroje E/H. Ręczny raport otrzymuje stabilną nazwę z sufiksem numerycznym przy kolizji; dane przebiegu są niezmienne.

**Nowy wymagany, niezaimplementowany typ `copper-faces`:** wyłącznie mapy E/H przy obu stronach każdej fizycznej warstwy miedzi, osobno per warstwa i strona, z częstotliwością, fazą, składowymi/modułem, orientacją XY, skalą, maską i statusem wiarygodności. Bez paneli impedancji, S11, SWR, wykresów portowych i odległych przekrojów. Diagnostyka/sondy portu mogą pozostać wewnętrznym źródłem normalizacji, ale nie są elementem raportu. K/straty AC wyłącznie po osobnej walidacji.

Rodzaj raportu wybiera zapisany kontrakt pomiaru, nigdy nazwa pliku/projektu. Nie wolno generować pozornych map z brakujących HDF5; stary `spatial-eh` musi zachować zgodność i możliwość regeneracji offline. Pełny kontrakt: [pcb-copper-surfaces.md](pcb-copper-surfaces.md).
