# Kontrakt outcomes, wersja 2

Każdy przebieg tworzy nowy katalog `outcomes/runs/<run_id>/`, pomijany przez Git.
ID zawiera czas UTC i losowy identyfikator. Po zakończeniu danych nie nadpisujemy.
Status wykonania jest niezależny od kontroli fizycznej.

| Etap | Stan po sukcesie | Co rzeczywiście wykonano |
| --- | --- | --- |
| `geometry` | `completed` | Generator, walidacja geometryczna i rysunek |
| `openems_input` | `prepared` | Dodatkowo natywne przygotowanie XML, bez FDTD |
| `simulation` | `completed` | Dodatkowo FDTD i postprocessing; nadal unverified |

Błąd lub przerwanie daje `failed` albo `cancelled`. Częściowe pliki i log
pozostają w katalogu. Nie przedstawiamy ich jako ukończonego wyniku.

## Aktualnie implementowane pliki

| Plik | Etap i zawartość |
| --- | --- |
| `manifest.json` | Wszystkie: etap, stan, czas, kod, solver, osie, normalizacja, ostrzeżenia, skróty SHA-256 |
| `parameters.resolved.json` | Wszystkie: pełna konfiguracja SI i odsyłacze do zapisanych schematów |
| `schemas/` | Wszystkie: kopie schematów przebiegu |
| `source.zip` | Wszystkie: źródła Python, schematy, parametry referencyjne i pyproject |
| `geometry.json` | Wszystkie: odcinki osi, promienie, płyta, port i założenia |
| `validation.json` | Wszystkie: kontrola geometrii; elektromagnetyka unverified |
| `plots/geometry.png` | Wszystkie: widoki xy/yz, bez rozkładu prądu |
| `mesh.npz`, `mesh.json` | prepare/run: linie x/y/z w m, rozmiar, wymuszenie, PML i NF2FF |
| `openems/model.xml` | prepare/run: pełne wejście FDTD i CSXCAD |
| `solver.log` | prepare/run: komunikaty natywnego procesu i postprocessingu |
| `openems/` | run: surowe pliki portu i powierzchni NF2FF |
| `port_spectra.npz` | run: widma portu i zespolony współczynnik normalizacji |
| `impedance.csv` | run: frequency_hz, resistance_ohm, reactance_ohm, reference_ohm, s11_real, s11_imag, swr |
| `far_field.npz` | run, gdy zażądano: zespolone pole dalekie, zysk i kierunkowość |
| `summary.json` | run: impedancja, SWR, opcjonalnie zysk +z i bilans mocy |
| `plots/impedance.png`, `plots/pattern_cuts.png` | run: impedancja i opcjonalne przekroje xz/yz pierwszej częstotliwości |
| `report.html` | run: lokalny raport z zapisanych danych |

Geometria ani prepare nie tworzą pól, impedancji lub zysku. Manifest zawsze
ma `validation_status=unverified`. Sukces testów geometrii tego nie zmienia.

## Konwencje danych

NPZ nie zawierają pickle; odczyt przez `np.load(..., allow_pickle=False)`.
Wymiary są w SI. Kierunek główny to +z, theta od +z, phi od +x ku +y.
E_theta i E_phi to składowe w lokalnej bazie sferycznej, nie automatycznie
składowe co/cross anteny.

`port_spectra.npz`:

- `frequency_hz` [nf];
- `voltage_fourier` i `current_fourier` [nf], zespolone transformaty impulsu;
- `native_power` [nf], 0,5 Re(V · conj(I)), w konwencji natywnego DFT;
- `normalization_factor` [nf], zespolony mnożnik amplitudy i fazy;
- `convention`, opis, dlaczego widma nie są amplitudami sinusoidalnymi.

`far_field.npz`:

- `frequency_hz` [nf], `theta_deg` [nt], `phi_deg` [np], bez podwójnego 360°;
- `e_theta_v_per_m` i `e_phi_v_per_m` [nf, nt, np], amplitudy szczytowe;
- `reference_distance_m` [1], promień asymptotycznego pola, obecnie 1 m;
- `gain_linear`, `directivity_linear`, `realized_gain_linear` [nf, nt, np];
- `radiated_power_w` [nf], `accepted_power_w` [1], `phasor_convention`.

Normalizacja: moc przyjęta, domyślnie 1 W, faza dodatniego maksimum
napięcia portu, rekonstrukcja Re(F · exp(+j · faza)). Manifest zawiera
konwencję i informację, czy ją zastosowano; mnożniki są w port_spectra.
S11 = (Z − Zref)/(Z + Zref), gdzie Zref jest rzeczywiste i dodatnie.
Realized gain nie dopisuje strat nieobecnego baluna, kabla lub LNA.

Schemat manifestu: `schemas/run-manifest.schema.json`. Lista skrótów nie
zawiera samego manifestu. Archiwum kodu zawiera tylko wybrane źródła;
nie zawiera kont, środowiska procesu ani DLL. Odtworzenie wymaga instalacji
zgodnego solvera i wskazania zapisanej konfiguracji.

## Planowane rozszerzenia M2/M3

Wymagania prądów i pól nie zostały usunięte. Nie ma jeszcze ich pliku ani
odczytu. Docelowo:

- `currents.npz`: częstotliwości, prąd zespolony, miejsce i kierunek próbki;
- `fields/xz.npz`, `fields/yz.npz`, `fields/xy_front.npz`: współrzędne,
  zespolone E/H, osie siatki, maski i przyczyny niewiarygodnych próbek;
- mapy faz 0–180° co 30° i pełny okres animacji przy wspólnej skali kolorów.

Próbki niewiarygodne będą oznaczane NaN i maską, nie sztucznym zerem.
Zmiany konwencji lub formatu wymagają nowej wersji kontraktu.
