# Aktualny priorytet — PCB copper-faces

Stan dokumentacyjny 2026-10-24. Nowy cel użytkownika zastępuje wcześniejszy priorytet rozwijania ogólnych raportów. **Nie jest zaimplementowany.** Szczegółowy kontrakt: [docs/pcb-copper-surfaces.md](docs/pcb-copper-surfaces.md). Punkt przejęcia: [migracja.md](migracja.md).

**Cel:** w obecnym GUI dwa tryby: dotychczasowy przestrzenny E/H i nowy E/H po obu stronach każdej fizycznej warstwy miedzi. Raport nowego trybu wyłącznie mapy E/H przy miedzi, bez S11, impedancji, SWR i odległych przekrojów. K dopiero po walidacji.

**Stan:** multilayer, GUI, stare dumpy i renderer istnieją. Nie istnieją per-face dumpy, osobny kontrakt danych ani renderer copper-faces. `pcb_sample_mask` maskuje właśnie bliską miedź; `report_data.py` wymaga widma. Miedź jest zerogrubościowym PEC/sheet; osobnych fizycznych prądów obu stron nie wolno deklarować bez weryfikacji.

**Pierwsza odpowiedzialność architektoniczna:** polityka pomiaru i fizyczny sampling Yee/openEMS, nie HTML. Zweryfikować pozycje próbek i jednostronne H/E na granicy PEC/sheet, z/warstwy, ośrodek, maski, koszt i zbieżność. Nie zastępować braków interpolacją z 1 mm.

**Kolejne zależności funkcjonalne:** trwały manifest typu pomiaru, GUI/CLI, postprocess niezależny od obowiązkowej impedancji, dwa renderery wybierane na podstawie danych, offline recovery i testy regresyjne. Bez nowego solvera, bez zmian anten/FAST, bez nadpisywania historycznych wyników.

**Odbiór:** dla czterech warstw osiem osobnych widoków XY, każdy z E/H, poprawne identyfikatory i pozycje, jawne brakujące próbki; stary tryb bez regresji; brak sekcji portowych w nowym raporcie. Natywny Windows openEMS i zbieżność pozostają OPEN.

Historyczne problemy: `stripline2_006` ma puste widma FD po przerwaniu; postprocess nie odtworzy brakujących pól. Zmiana nazw ręcznych HTML w ba323c3 nie dotyczy nowego trybu. Nie wykonywano testów ani FDTD w tym checkpointcie.
