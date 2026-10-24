# PCB GUI — aplikacja okienkowa Windows

Aplikacja `antenna_lab.pcb.gui` jest prostym interfejsem Tkinter do **istniejących**
narzędzi `.epro`, openEMS i raportów. Nie implementuje drugiego solvera,
nie przepisuje fizyki, nie zmienia siatki ani nie wymaga dodatkowych bibliotek
GUI poza standardowym Pythonem z Tkinter.

## Uruchomienie

W katalogu repozytorium na Windows 11 kliknij dwukrotnie:

**`PCB_GUI.bat`**

lub w CMD:

```bat
.\.venv\Scripts\python.exe -m antenna_lab.pcb.gui
```

Jeśli okno nie otworzy się przy podwójnym kliknięciu, użyj wariantu CMD,
aby zobaczyć błąd uruchamiania; launcher korzysta z `pythonw.exe`
w lokalnym `.venv`. Dla natywnego solvera sprawdź pole
`CSXCAD_INSTALL_PATH` (zwykle `C:\dev\openems\openEMS`).

## Obsługa

1. **Wybierz projekt**: dowolne dostępne lokalnie `.epro`. GUI sam
   wyznacza i tworzy folder ustawień `parameters/<folder_projektu>/` i
   wyświetla jego pełną ścieżkę pod polem pliku (przycisk **Otwórz parametry**).
   Po zmianie folderu automatycznie wczytuje właściwy `gui-settings.json`.
   Kilka plików `.epro` w jednym folderze współdzieli ustawienia solvera
   i eksperymentu; ręczny `source-config` i ostatni przebieg są osobne.
2. **Sprawdź projekt**: używa istniejącego
   `antenna_lab.pcb.reduced_control --inspect-source`, bez FAST solve,
   mesh/FDTD i bez plików Gerber. Nieznane typy rekordów CAD pozostają błędem.
3. **Ustaw eksperyment i solver**: edytuj center/cutoff, sweep od/do/co,
   częstotliwości pól E/H, profil, rozdzielczość geometrii, ewentualnie
   `--openems-set KEY=VALUE` (po jednej wartości w wierszu). Wszystkie
   częstotliwości z GUI są w MHz.
4. **Przygotuj siatkę**: `--prepare-only`; liczba komórek i audyty
   pozostają w logu oraz zapisanym `summary.json`. Nie uruchamia FDTD.
5. **Uruchom FDTD**: przed startem pokazuje parametry i pyta o potwierdzenie.
   Jeżeli w tej sesji GUI nie wykonano pomyślnego PREPARE-ONLY **dla dokładnie
   tych samych parametrów**, GUI ostrzega dodatkowo. Wyniki trafiają do
   katalogów `outcomes/pcb_easyeda/<nazwa_pliku>_NNN`, bez nadpisywania.
6. **Raport i pola**: można wskazać dowolny istniejący katalog FDTD,
   również z poprzedniej sesji. Ustaw `active+geometry`, próg -40 dB,
   margines 1 mm i krok fazy 15°. Raport HTML powstaje z istniejących
   CSV/NPZ, otwiera się w przeglądarce i nie uruchamia FDTD.
   Domyślnie GUI wykonuje ten krok również po pomyślnym uruchomieniu FDTD.

GUI na żywo wypisuje log, ścieżkę wyniku i pełne polecenie CMD.
Przyciskiem **Kopiuj** można je przenieść do terminala. Faktyczne
wykonanie odbywa się przez `subprocess` z listą argumentów i `shell=False`;
interfejs nie interpretuje ciągów znaków jako poleceń powłoki.

`--source-config` jest opcjonalny. Jeżeli nie zostanie wskazany,
istniejący importer sam rozwiązuje źródło oraz idealne wartości R/L/C
z `.epro` i zapisuje kontrakt w plikach wyniku. **Nie zgadujemy**
niezapisanej w CAD grubości PTH: opcjonalne pole `PTH metalizacja`
to jawnie podana przez użytkownika wartość w µm.

## Zakładka Warstwy EM

Po wskazaniu `.epro` GUI odczytuje rzeczywisty `LAYER_PHYS` bez
uruchamiania FDTD. Pokazuje miedź (TOP, aktywne fizycznie SIGNAL/PLANE,
BOTTOM), warstwy dielektryczne SUBSTRATE z Z/grubością oraz εr/tanδ.
Świadomie pomija silk, paste, mask, stencil i inne nieelektryczne
warstwy edytora. Nie dodaje soldermaski ani jej wpływu na εr —
to przyszły, jawnie przybliżony model.

Jeżeli EasyEDA nie dostarczył fizycznej εr (np. 0), pole pozostaje
puste. Użytkownik uzupełnia dokładnie brakujące wartości w tabeli;
GUI generuje `--dielectric-material ID:epsilon_r:tan_delta` dla
odpowiednich warstw i utrwala w projektowych `gui-settings.json`.
Nie tworzy się ręcznie konfiguracji JSON i nie stosuje niewidocznych
domyślnych materiałów. Nieprawidłowa εr lub nieznany ID blokują
PREPARE-ONLY/FDTD przed rozpoczęciem kosztownych obliczeń.

## Katalog parametrów przypisany automatycznie do projektu

Dla typowej ścieżki `gerbs/dif4002/dif4002.epro` GUI tworzy lub otwiera
`parameters/dif4002/`. Jeżeli w `gerbs/projekt/` są
`projekt1.epro` i `projekt2.epro`, **oba korzystają z
`parameters/projekt/`**. Identyfikatorem katalogu jest zatem ścieżka
*folderu projektu pod gerbs*, nie nazwa każdego osobnego dokumentu `.epro`.
Ta stabilna reguła działa także po dodaniu kolejnych plików w folderze.
Dla `.epro` bezpośrednio pod `gerbs/` używa się nazwy pliku bez rozszerzenia;
dla plików spoza `gerbs/` stosuje się nazwę folderu i stabilny skrót
jego pełnej ścieżki, aby różne zewnętrzne projekty się nie mieszały.

GUI zapisuje własny plik `gui-settings.json` atomowo już po wyborze projektu,
a następnie przy zmianie projektu, uruchomieniu etapu i zamknięciu aplikacji. Zawiera wyłącznie edytowalne
ustawienia eksperymentu, profilu i pól, jawne nadpisania openEMS oraz
opcjonalną metalizację PTH. **Nie przenosi między dokumentami `.epro`**
ręcznego JSON-a source-config, identyfikatora PCB ani katalogu wyników.
Brak katalogu powoduje jego utworzenie. Inne pliki w `parameters/`
nie są usuwane ani nadpisywane.

Ścieżka instalacji biblioteki `CSXCAD_INSTALL_PATH` pozostaje
**ustawieniem środowiska komputera**, dlatego nie przełącza się razem z
projektem. Plik profili `parameters/openems_profiles.toml` nadal jest
wspólną konfiguracją bazową solvera; wybór profilu i edytowane override
są zapisane oddzielnie dla folderu projektu.

Globalny plik `~/.antenna_lab_pcb_gui.json` pamięta jedynie ostatnio
otwarty projekt i ścieżkę CSXCAD. Nowe lokalne
`parameters/**/gui-settings.json` są wykluczone z Git. Polecenia CLI,
surowa geometria i pełna konfiguracja rzeczywistego przebiegu pozostają
utrwalone w istniejących artefaktach FDTD.

## Bezpieczeństwo i ograniczenia

- GUI jest nakładką na CLI; wyłącznie jego walidacja i logika solvera
  rozstrzygają, czy projekt da się zasymulować. Samo otwarcie .epro
  nie stanowi potwierdzenia poprawnej geometrii.
- Przerwanie procesu natywnego może pozostawić niekompletne wyniki.
  GUI nie usuwa ich, nie oznacza jako `completed` i nie uruchamia ponownego FDTD.
- Jeden etap działa naraz. Brak sztucznego paska procentowego postępu
  FDTD: raportowane są rzeczywiste komunikaty silnika.
- Gdy brak poprawnych pól, raport nie może ich odtworzyć wyłącznie z S11.
  Weryfikuj `stages.fields`, `fields/metadata.json` i pliki NPZ.
- Domyślne wartości częstotliwości są tylko **edytowalnym przykładem**
  eksperymentu, nie są odczytane z nowego projektu CAD.
- Testy jednostkowe GUI obejmują generowanie komend bez uruchamiania
  grafiki, native FDTD ani PSU. Rzeczywista integracja z Windows i CSXCAD
  wymaga osobnego uruchomienia użytkownika.

Weryfikacja czystej warstwy komend:

```bat
.\.venv\Scripts\python.exe -X utf8 -m unittest discover -s tests -p test_pcb_gui_commands.py -v
```

## Dopasowanie pasma pobudzenia do sweep

Sweep określa częstotliwości, w których mają powstać wykresy Z/S11;
środek i odcięcie opisują osobno szerokopasmowe pobudzenie solvera.
Backend wymaga: `sweep ⊆ [center − 0.8·cutoff, center + 0.8·cutoff]`.
GUI stosuje **identyczną walidację przed PREPARE-ONLY/FDTD** i podaje
dozwolony zakres oraz zalecaną poprawkę w komunikacie.

Przycisk **Dopasuj pobudzenie do sweep** po jawnej decyzji użytkownika
wylicza `center=(sweep_start+sweep_stop)/2` i
`cutoff=(sweep_stop−sweep_start)/1.6`. Ustawienia nie są zmieniane
samoczynnie podczas uruchamiania solvera. Dla sweep 100–900 MHz dostajemy
center=500 MHz, cutoff=500 MHz; trzy pola E/H przy 200/500/800 MHz
pozostają poprawne. Do oceny dokładności częstotliwości brzegowych
stosuj niezależne sprawdzenia zbieżności; spełnienie guardu nie jest
walidacją fizyki.

## Tryb map powierzchni miedzi (2026-10-24)

W zakładce Eksperyment pojawił się wybór `far` (stare przekroje E/H)
lub `copper_surfaces` (każda fizyczna warstwa Cu od góry i od dołu).
Wybór jest zapisywany osobno dla folderu projektu EasyEDA razem z
pozostałymi ustawieniami. CLI wykorzystuje `--field-mode copper_surfaces`
i nadal wymaga zaznaczonego zapisu pól oraz 1–3 częstotliwości.
To **zmienia siatkę Z** przez wstawienie sond 10 µm od powierzchni;
przed FDTD wykonaj PREPARE-ONLY i zweryfikuj CFL oraz liczbę komórek.
Tryb przygotowuje dedykowany raport powierzchniowy bez S11/SWR/impedancji.
Kontrakt i warunki walidacji: [pcb-copper-surfaces.md](pcb-copper-surfaces.md).
