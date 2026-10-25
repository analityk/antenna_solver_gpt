# PCB — mapy gęstości prądu na miedzi (pierwszy tor diagnostyczny)

**Stan na 2026-10-25:** ukończono rzeczywiste FDTD dla `stripline4_004` na Windows i przetworzono dane prądu na czterech warstwach. Ilościowa fizyka estymaty K nadal ma status **UNVERIFIED**. Raport korzysta wyłącznie z **kontrastowych PNG fazowych co 15° z Play/Pause**; wcześniejsze widoki globalnej skali liniowej i statyczne pary 0°/90° są historycznym rozwiązaniem, **nie są już wyświetlane**. Solver antenowy bez zmian.

## Konkretny przypadek: gerbs/stripline4/stripline4.epro

Archiwum ZIP zawiera fizyczny stos **TOP / Inner1 / Inner2 / BOTTOM**, trzy dielektryki 361 / 362 / 363, pięć nazwanych sieci `TX`, `GND`, `+5V`, `3V`, `1V`, osiem komponentów i dziesięć rekordów VIA. W `LAYER_PHYS` pola fizycznej przenikalności dielektryków są niezdefiniowane/zerowe — to nie znaczy εr=0. Do symulacji trzeba wpisać **świadomie wybrane wartości εr oraz tanδ**, odpowiednie dla materiału i interesującej częstotliwości. Jeżeli metalizacja PTH nie wynika jednoznacznie z CAD, dotychczasowy preflight wymaga jej podania. Nie uzupełniać materiałów ani galwanizacji domyślną wartością.

## Jak uzyskać pierwszą mapę na Windows 11

1. `git pull --ff-only`; uruchom aplikację `PCB_GUI.bat`.
2. Wybierz `gerbs/stripline4/stripline4.epro`. Użyj istniejącego `Inspekcja`, aby potwierdzić aktywną płytkę, miedź, komponenty i źródło.
3. W zakładce materiałów EM przypisz do trzech warstw dielektryka własne εr i tanδ; uzupełnij PTH plating, jeżeli zgłosi go preflight. Nie wpisuj fikcyjnych danych tylko po to, żeby symulacja ruszyła.
4. W ustawieniach eksperymentu wybierz pasmo pobudzenia i częstotliwość mapy w polu **Pola przy**. Zaznacz `Zapisz pola E i H` oraz **`Mapa prądu na wszystkich warstwach miedzi (rot H; wynik eksperymentalny)`**. Częstotliwości muszą mieścić się w zadanym sweep i paśmie skutecznego pobudzenia.
5. Uruchom **PREPARE-ONLY**, obejrzyj liczbę komórek, zakres dumpów, pozycje warstw, informacje o materiałach i porcie. Żadna część przygotowania nie uruchamia FDTD.
6. Dla **nowego** przypadku po preflight uruchom FDTD; dla **istniejącego `stripline4_004`** NIE uruchamiaj solvera, lecz otwórz zakładkę Raport i wygeneruj HTML z zapisanych wyników. Sekcja **Gęstość prądu na miedzi — animacja fazowa** zawiera jeden odtwarzacz PNG dla każdej warstwy i częstotliwości: fazy 0°–345° co 15°, suwak, Play/Pause. Używa wyłącznie kontrastu lokalnego.
7. Gdy obliczenie się przerwie, skorzystaj z dotychczasowego `postprocess` (w osobnym katalogu) dla odzyskania **faktycznie istniejących** HDF5. Pusty `FieldData/FD` daje status `failed` i przyczynę, nie udawaną zerową gęstość prądu.

Opcjonalny CLI to dotychczasowe `python -m antenna_lab.pcb.easyeda_control` z przełącznikiem `--surface-current` **razem z** `--fields-mhz` i kompletnymi parametrami modelu; tryby `--prepare-only` / `--yes` pozostają bez zmian. Zapis prądu nie jest włączony w dawnych przebiegach ani w antenowym solverze Quados/biquad.

## Co dokładnie jest liczone

- Dla każdej obsadzonej warstwy miedzi kod dodaje jeden natywny dump openEMS `dump_type=13`, `dump_mode=1`, `file_type=1`. To **częstotliwościowa gęstość prądu całkowitego `rot(H)` [A/m²]**, a nie natywnie bezpośredni powierzchniowy K.
- Pozycja Z dumpu jest dokładnie istniejącą linią siatki w miejscu modelowanego sheetu; brak zgodności powoduje błąd, bez przesuwania płaszczyzny. Brak limitu czterech warstw. `MAX_FIELD_POINTS` ogranicza sumę pozycji/częstotliwości dla ochrony pamięci; użytkownik zmienia parametry jawnie.
- Postprocessing wyznacza **estymatę** `K_est = rot(H)_t * dual_width_z` w [A/m], gdzie `dual_width_z = (z[k+1] - z[k-1])/2`. To metoda podobna do wykorzystanej w [Fairbeam](https://github.com/ismailakdag/fairbeam/blob/main/python/fairbeam/fields.py), lecz w przeciwieństwie do Fairbeam zachowuje nieznormalizowane zespolone składowe i deklarowaną jednostkę estymaty. **Dokładność absolutna nie jest jeszcze potwierdzona.**
- Pełne `native/pcb_curlH_XXX.h5` pozostają nienaruszone; `currents/pcb_curlH_XXX.npz` zawiera fazory, skalowanie do 1 V portu, rzeczywistą siatkę, `on_copper` i dual-width. `currents/metadata.json` przechowuje pochodzenie, status i ograniczenia. Maska odcina tylko obszar poza fizyczną geometrią miedzi; *nie* odcina otoczenia metalu na przekątnej komórki, jak stara E/H.
- Kolor animowanej klatki = **chwilowy moduł** `|K(t)| = |Re(K * exp(+j * phi))|`, a strzałki pokazują jednocześnie chwilowy kierunek. Skala kontrastu jest logarytmiczna i **stała przez 24 fazy** danej pary warstwa/częstotliwość; jej górny próg to percentyl 99,5 dodatniego modułu **fazora**, aby nie „pompować” jasności między fazami. Barw nie wolno porównywać bezwzględnie między różnymi warstwami ani częstotliwościami. Pełne zespolone NPZ pozwalają wykonać niezależne porównania ilościowe; piki na krawędziach wymagają weryfikacji.

## Czego wynik NIE oznacza

Nie jest to jeszcze zweryfikowane `K_net = n × (H_plus − H_minus)`, ani osobne K górnej i dolnej fizycznej powierzchni folii 35 µm, ani objętościowy rozkład `J` przez miedź. Nie pozwala bez osobnej walidacji obliczyć strat AC, skin effect, ilościowych pików na ostrych narożach czy rozkładu ładunku `rho_s`. Materiał typu conducting sheet oraz lokalne porty/via wymagają szczególnej oceny. Brak ręcznych danych εr/tanδ, metalizacji lub nieskuteczne wzbudzenie oznacza brak wiarygodnej symulacji, niezależnie od jakości mapy. Obecny model portu i normalizacja 1 V mają status `unverified`.

**Warunek odbioru kolejnego etapu:** użytkownik otwiera raport z natywnego FDTD dla `stripline4` i stwierdza, czy prąd płynie po spodziewanych sieciach, czy cztery warstwy są rozdzielone, czy faza i skala są użyteczne. Następnie porównujemy wyniki na zagęszczonej siatce i metodą granicznych skoków H. Dopiero po takim odbiorze wolno nazywać K wynikami ilościowymi i przejść do ładunku/pól jednostronnych. Gdy dump nie daje użytecznej wartości — zatrzymujemy tę gałąź, zachowujemy dane i wybieramy metodę alternatywną, zamiast rysować fikcyjne prądy.

Źródła: [openEMS: dump_type/dump_mode](https://docs.openems.de/en/latest/python/CSXCAD/CSProperties/CSPropDumpBox.html), [openEMS: HDF5 / siatka](https://docs.openems.de/en/latest/concepts/dump_hdf5.html), [Fairbeam](https://fairbeam.org/docs/bundle.html), [wymaganie docelowe](pcb-current-charge-goal.md).

## Stripline4_004 — prawdziwy przebieg i widoki z kontrastem

Użytkownik przeprowadził 48488 kroków FDTD w 5282,8 s, a openEMS wypisał: `RunFDTD: end-criteria of -40.00dB reached ... (-41.29dB)`. Raport potwierdza pełną ścieżkę danych `currents: processed` dla czterech warstw × 1 i 2 GHz. Jednocześnie `openEMS_stats.txt` nie został znaleziony, dlatego formalny status ukończenia czasowego pozostaje `unconfirmed` mimo informacji w konsoli. Ilościowa dokładność K pozostaje `unverified`.

**Ważne:** dla dielektryków 361/362/363 wpisano εr=4 i **tanδ=1.001**, nie 0.001. To ekstremalnie stratny model w porównaniu z typowym laminatem PCB — trzeba to potwierdzić z kartą materiałową przed nowym kosztownym solve. Grubości miedzi wewnętrznej pokazane w raporcie to ~350 µm, zewnętrznej ~35 µm; obecna miedź PEC ignoruje te grubości.

Dotychczasowe mapy używają wspólnej skali liniowej ~450 A/m/1 V, przez co słabsze struktury są niemal niewidoczne. **Historyczny stan raportu (`stripline4_004__003.html`):** obok liniowej mapy pojawił się kontrast log-p99,5. **Stan obecny:** decyzją użytkownika usunięto oba stare układy z raportu na rzecz samych kontrastowych klatek PNG co 15° z odtwarzaczem. Porównanie ilościowe wykonuje się ze źródłowych NPZ, a nie ze skali jasności między warstwami. Re-render dla istniejącego `stripline4_004` nie uruchamia FDTD i nie modyfikuje HDF5/NPZ.


### Odbiór widoków lokalnych na rzeczywistym stripline4_004

Użytkownik dostarczył `stripline4_004__003.html`, który po hotfiksie `68db056` zawiera 16 map K_est: każda z 4 warstw przy 1 i 2 GHz ma mapę globalną i kontrast lokalny. Wizualizacyjna bramka została przyjęta na podstawie faktycznego raportu (VISUAL PASS). Z maksimum K_est w [A/m na 1 V] dla TOP: 207.889/142.201, Inner1: 459.697/317.901, Inner2: 139.073/96.4736, BOTTOM: 52.1976/35.9828 (odpowiednio 1/2 GHz). W szczególności silniejszy pik na Inner1 nie dowodzi całkowitego prądu uzwojenia, a widok log/p99,5 nie pozwala porównać mocy między warstwami. Widoki faz 0°/90° różnią się tylko wektorami; moduł barwny jest celowo wspólny. **Nie uzyskano dotąd ilościowej walidacji `rot(H)→K`**, ponieważ przesłano HTML, nie natywne NPZ. Następna porcja analizy dotyczy już tylko istniejących plików wynikowych, bez FDTD.

## Aktualny odtwarzacz PNG: jedna warstwa i częstotliwość = 24 klatki

**Decyzja użytkownika:** kolor ma przedstawiać moduł K, obraz jest PNG (nie canvas), a w raporcie ma być **wyłącznie lokalny kontrast**, bez równoległego widoku liniowego. Z uwagi na cel pokazywania zmian z fazą kolor oznacza **moduł chwilowego wektora** `|Re(K·exp(jφ))|` [A/m dla portu 1 V]; **nie** niezmienną w fazie zespoloną obwiednię `|K|`. Kierunek podpisanego prądu odczytuje się ze strzałek. Każda klatka powstaje z pierwotnych NPZ — bez kolejnego FDTD.

- Dla każdej warstwy/f odtwarzacz ma `Play/Pause`, suwak `0°…345°`, krok `15°` i 24 zapisane obrazy PNG. W projekcie `stripline4_004` są 4 warstwy i 2 częstotliwości, więc osiem niezależnych odtwarzaczy/192 klatki. Nie ma kodowego limitu liczby warstw.
- HTML jest samodzielny: obrazy PNG są osadzone w `data:image/png;base64` przez wspólny `figure_image`. JavaScript jedynie przełącza gotowe klatki; żadne próbki pola nie są w nim ponownie obliczane. Raport wygenerowany automatycznie zapisuje też pliki PNG w `plots/current_phase_*`; raport ręczny jest samodzielnym HTML. Nie korzysta z internetu.
- Maska obejmuje wyłącznie modelowaną miedź; strzałki dobierane są na istniejących próbkach miedzi, żeby siatka podpróbkowania nie omijała wąskich ścieżek. Skala log-p99,5 jest obliczana **jeden raz** z obwiedni zespolonej danej warstwy/f i utrzymana bez zmian przez pełny obrót. Jasność różnych warstw nie jest porównywalna; normalizacja fazorów i jednostki w NPZ zostają zachowane.
- Cena wyboru PNG: samodzielny HTML może być zauważalnie większy niż dawny raport, a ponowne renderowanie trwa dłużej. To **tylko etap raportowania**, nie solvera. Suwak i Play/Pause nie uruchamiają Pythona ani openEMS.
- **Bramka testowa:** numeryczny test `current_at_phase`, generowanie prawdziwego PNG dla obu różnych faz, 24 klatki w każdej sekcji, oraz zachowanie archiwalnych NPZ. Na Windows użyć `.\\.venv\\Scripts\\python.exe -X utf8 -m unittest discover -s tests -p test_pcb_currents.py -v`; następnie wygenerować wyłącznie raport istniejącego `stripline4_004` i ręcznie obejrzeć Play/Pause. Natychmiastowe obrazy podglądowe mogą pochodzić z wcześniej przesłanych NPZ.

**Ograniczenia fizyczne bez zmian:** metoda `rot(H)→K_est` nie jest jeszcze zweryfikowaną jednostronną rekonstrukcją `n×(H_plus-H_minus)`; brak warunków dokładnych przy portach, vias i ostrych krawędziach. Materiały w wykonanym przebiegu mają `tanδ=1.001`, wymaga to odrębnego potwierdzenia. Kryterium czasowe w logu FDTD zostało osiągnięte, natomiast raport nie znalazł `openEMS_stats.txt`.
