# Historia — checkpoint 2026-10-24

Dokumentacyjna rekonstrukcja po urwanej rozmowie. Odczytano repozytorium `analityk/antenna_solver_gpt`, gałąź `main` na `ba323c333ba86162c9bd55df4555658b25970349`, dokumenty i implementację pomiarów/raportów. **Nie zmieniano kodu, nie wykonywano testów ani FDTD.**

Użytkownik zmienił priorytet: zachować obecny przestrzenny E/H i dodać w tym samym GUI alternatywny pomiar E/H tuż po obu stronach każdej warstwy miedzi; raport nowego trybu ma pokazywać wyłącznie te mapy, bez impedancji/S11/SWR. Osobny typ raportu musi odpowiadać zapisanym danym. Nie tworzyć niezależnego solvera.

Rozpoznane ograniczenia: trzy sztywne płaszczyzny w `solvers/pcb_fields.py`; maska halo wycina próbki blisko metalu; renderer rozpoznaje tylko istniejące nazwy; raport jest sprzężony z widmem portowym. Folia w solverze jest zerogrubościową PEC/conducting sheet, zatem skok H może reprezentować prąd wypadkowy, ale nie dowodzi niezależnych prądów dwóch fizycznych stron. Wcześniejsza rozmowa miała błędne wzory Rs i J; skorygowano je w nowej specyfikacji.

Kontrakt i warunki odbioru: `docs/pcb-copper-surfaces.md`. Aktualny punkt przejęcia: `migracja.md`; priorytet: `todo.md`. Historyczne dane i testy pozostawiono nietknięte.
