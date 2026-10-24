# PCB GUI — aktualny stan i wymagany wybór trybu

Istniejący Windows Tkinter GUI obsługuje EasyEDA .epro, inspect, prepare, run i raport. Formularz pozwala wybrać częstotliwości pól i kadrowanie istniejących przekrojów. **Nie ma jeszcze wyboru pomiaru po obu stronach miedzi.**

Nowy cel: jedna aplikacja i dwa rozłączne tryby pomiaru: `spatial-eh` (dotychczasowe przekroje E/H) albo `copper-faces` (osobne E/H XY od +Z i -Z każdej warstwy). Wybór należy do parametrów eksperymentu zapisanych per projekt i manifestu FDTD; prepare i run muszą używać tego samego wyboru. Raport wybiera typ z rzeczywiście zebranych danych, nie z aktualnego ustawienia GUI. W `copper-faces` nie pokazuje S11, impedancji, SWR ani odległych pól. Wybór kadrowania nie zastępuje próbkowania przy miedzi.

Wymagania, ograniczenia PEC/sheet i kryteria odbioru: [pcb-copper-surfaces.md](pcb-copper-surfaces.md). Stan: specyfikacja, bez zmiany kodu i bez testów.
