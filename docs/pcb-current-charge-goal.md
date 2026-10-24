# Korekta celu fizycznego: planar transformer, current crowding i fringing

Checkpoint 2026-10-24. Niniejsza korekta **zastępuje** fragmenty wcześniejszej specyfikacji, w których K określono jako opcjonalne, a docelowy wynik ograniczono do E/H. Stan: wymaganie, nie funkcja gotowa.

## Wynik wymagany
Dla każdej warstwy miedzi, dla obu stron (+z/-z), zachować zespolone, jednostronne pola E i H, a z ich granicznych skoków wyprowadzić i przedstawić:
- **K_net [A/m]**: powierzchniowa gęstość prądu wypadkowego sheetu, kierunek i moduł, faza, mapa current crowding.
- **rho_s_net [C/m²]**: powierzchniowa gęstość ładunku wypadkowego, mapa modułu, znaku/fazy, rozkład przy krawędziach i szczelinach.
- **E/H**: osobno dla stron i warstw, w tym pola między przewodnikami i fringing. Nie zastępować tych wyników S11, impedancją lub SWR.
- Opcjonalnie po walidacji: odrębne prądy/ładunki rzeczywistych powierzchni górnej i dolnej folii oraz straty AC. Nie mylić ich z K_net/rho_s_net.

## Warunki fizyczne
Dla normalnej n od -z do +z, przy konsekwentnej orientacji i przy braku dodatkowych nieujętych prądów:
`K_net = n × (H_plus − H_minus)`.
`rho_s_net = n · (D_plus − D_minus)`, `D = epsilon * E` w odpowiednim ośrodku. Są to skoki pól na powierzchni sheetu, nie wartości na dowolnych odległych płaszczyznach. W harmonicznym stanie ustalonym sprawdzać ciągłość ładunku `div_s K + j*omega*rho_s = 0` z uwzględnieniem portów, przejść i połączeń. Dla PEC w przewodniku nie ma pola; przy finite-conductivity sheet nie zakładać automatycznie tego samego jednostronnego warunku.

Sheet zerowej grubości może mieć różne pola po obu stronach, zależne od pozostałych przewodników i sprzężenia. Różnica H daje prąd **wypadkowy** sheetu; różnica D daje ładunek **wypadkowy** sheetu. To nie jest dowód niezależnych prądów lub ładunków dwóch fizycznych powierzchni folii o niezerowej grubości. K i rho_s są **obowiązkowym celem produktu**, lecz raport nie może deklarować ich jako wiarygodnych, zanim nie przejdą testów jednostronnego próbkowania i walidacji.

## Przypadki inżynierskie
Planarny transformator: sąsiednie uzwojenia i warstwy, proximity effect, koncentracja prądu przy krawędziach, prądy powrotne, rozkład ładunku, fringing przy końcach ścieżek i szczelinach. Porównanie wariantów geometrii przy zgodnych wymuszeniach i skalach. Wymagana jest weryfikacja modelu portów, połączeń i rzeczywistych dróg prądowych; mapa barw nie dowodzi poprawności fizycznej.

## Konsekwencje architektoniczne
Najpierw udowodnić, że dumpy openEMS/siatka Yee dają jednostronne wartości graniczne E/H przy PEC i conducting sheet (a nie node-interpolation mieszającą strony). Zweryfikować z, ośrodek, normalne, maski, krawędzie, połączenia między warstwami, siatkę i zbieżność. Następnie trwały kontrakt E/H/K/rho_s z flagami wiarygodności, postprocess i raport `copper-faces`; GUI wybiera ten tryb obok dotychczasowego przestrzennego E/H. W raporcie docelowo E/H obu stron oraz K i rho_s, bez S11/impedancji/SWR. Brak wiarygodnych próbek ma blokować lub jawnie oznaczać odpowiedni wynik; nie zastępować go estymacją z 1 mm. Wartości przy idealnie ostrych krawędziach mogą być osobliwe i zależne od siatki; porównywać również wielkości całkowe i zbieżność.

Powiązanie: `docs/pcb-copper-surfaces.md`, `docs/fields.md`, `docs/reports.md`, `todo.md`, `migracja.md`. Jeśli dokumenty te określają K jako opcjonalny, niniejsza decyzja użytkownika ma pierwszeństwo.
