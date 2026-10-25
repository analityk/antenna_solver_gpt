# PCB — mapy gęstości prądu na miedzi (pierwszy tor diagnostyczny)

**Stan na 2026-10-26:** ukończono rzeczywiste FDTD dla `stripline4_004` na Windows i przetworzono dane prądu na czterech warstwach. Ilościowa fizyka estymaty K nadal ma status **UNVERIFIED**. Raport korzysta już wyłącznie z **kontrastowych animowanych GIF-ów z 24 klatkami co 15°**, osadzonych w zwijanych sekcjach. Starsze widoki liniowe, statyczne PNG i suwak Play/Pause dla prądu są rozwiązaniami historycznymi. Solver antenowy bez zmian.

## Konkretny przypadek: gerbs/stripline4/stripline4.epro

Archiwum ZIP zawiera fizyczny stos **TOP / Inner1 / Inner2 / BOTTOM**, trzy dielektryki 361 / 362 / 363, pięć nazwanych sieci `TX`, `GND`, `+5V`, `3V`, `1V`, osiem komponentów i dziesięć rekordów VIA. W `LAYER_PHYS` pola fizycznej przenikalności dielektryków są niezdefiniowane/zerowe — to nie znaczy εr=0. Do symulacji trzeba wpisać **świadomie wybrane wartości εr oraz tanδ**, odpowiednie dla materiału i interesującej częstotliwości. Jeżeli metalizacja PTH nie wynika jednoznacznie z CAD, dotychczasowy preflight wymaga jej podania. Nie uzupełniać materiałów ani galwanizacji domyślną wartością.

## Jak uzyskać pierwszą mapę na Windows 11

1. `git pull --ff-only`; uruchom aplikację `PCB_GUI.bat`.
2. Wybierz `gerbs/stripline4/stripline4.epro`. Użyj istniejącego `Inspekcja`, aby potwierdzić aktywną płytkę, miedź, komponenty i źródło.
3. W zakładce materiałów EM przypisz do trzech warstw dielektryka własne εr i tanδ; uzupełnij PTH plating, jeżeli zgłosi go preflight. Nie wpisuj fikcyjnych danych tylko po to, żeby symulacja ruszyła.
4. W ustawieniach eksperymentu wybierz pasmo pobudzenia i częstotliwość mapy w polu **Pola przy**. Zaznacz `Zapisz pola E i H` oraz **`Mapa prądu na wszystkich warstwach miedzi (rot H; wynik eksperymentalny)`**. Częstotliwości muszą mieścić się w zadanym sweep i paśmie skutecznego pobudzenia.
5. Uruchom **PREPARE-ONLY**, obejrzyj liczbę komórek, zakres dumpów, pozycje warstw, informacje o materiałach i porcie. Żadna część przygotowania nie uruchamia FDTD.
6. Dla **nowego** przypadku po preflight uruchom FDTD; dla **istniejącego `stripline4_004`** NIE uruchamiaj solvera, lecz wybierz zakładkę Raport. Sekcja **Gęstość prądu na miedzi — animacja GIF** zawiera jeden zwijany GIF na warstwę i częstotliwość, 24 fazy po 15°, kontrast lokalny. Nie ma suwaka ani przycisku Play; GIF zapętla się samoczynnie.
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

## Aktualny GIF: jedna warstwa i częstotliwość = jedna animacja (2026-10-26)

**Ostateczna decyzja użytkownika:** zamiast odtwarzacza PNG ma być **jeden animowany GIF** dla każdej pary warstwa/częstotliwość. Krok fazy nadal wynosi **15°**, a kolor w każdej klatce oznacza **moduł chwilowej wartości prądu** `|K(t)| = |Re(K·exp(jφ))|`, kierunek pokazują strzałki. Nie ma konkurencyjnych liniowych map ani kontrolek suwaka/Play/Pause. GIF jest osadzony w raporcie jak zwykłe zdjęcie, w natywnym `<details><summary>` z „dziubkiem” po lewej. Rozwinięcie pokazuje animację, zwinięcie ukrywa ją.

- Dane źródłowe: już zapisane zespolone `currents/*.npz`. Dla `stripline4_004`: **4 warstwy × 2 częstotliwości = 8 zwijanych GIF-ów**, każdy po **24 klatki** (0°…345°, krok 15°). Nie ma sztucznego limitu warstw.
- Matplotlib wylicza i rysuje 24 klatki z jedną, stabilną przez cały cykl, skalą log-p99,5 na parę warstwa/f. Pillow koduje obrazy w jeden GIF z **jedną stałą paletą Viridis/grayscale** przez 24 fazy, aby kolor nie zmieniał znaczenia między klatkami. Klatki odtwarzają się w nieskończonej pętli co **180 ms**, również offline. Kolory różnych warstw/f nie są bezwzględnie porównywalne.
- Jeden plik GIF jest osadzany w samodzielnym HTML przez `data:image/gif;base64`. Przy automatycznym raporcie kopia GIF ląduje też w `plots/current_phase_*.gif`; ręczny `antenna_lab report` nie wymaga tworzenia zewnętrznych obrazów. Nie ma zewnętrznego JS, sieci ani ponownego FDTD.
- GIF ogranicza liczbę kolorów do 256 i nie pozwala wybrać dokładnej fazy przez suwak. Użytkownik zaakceptował tę zamianę dla prostoty oglądania. Pełne fazory w NPZ/HDF5 są zachowane do ilościowej analizy.
- Do jawnych zależności projektu dodano `Pillow>=10.0`. Na Windows po `git pull --ff-only` uruchomić `.\\.venv\\Scripts\\python.exe -X utf8 -m unittest discover -s tests -p test_pcb_currents.py -v`, potem **tylko re-render** raportu z istniejącego `outcomes\\pcb_easyeda\\stripline4_004`. Nie trzeba ponawiać 88-minutowego solvera.

**Odbiór fizyczny otwarty:** dotychczasowy `K_est` pozostaje niezweryfikowanym ilościowo przybliżeniem `rot(H)_t·dual_width_z`; nie jest to rozkład J wewnątrz folii, ani dowód poprawności prądów przy PTH/portach. Dla `stripline4_004` przyjęto `tanδ=1.001`, co należy potwierdzić przed następnym kosztownym FDTD; w raporcie brakło osobnego `openEMS_stats.txt` mimo wyraźnego ukończenia według natywnego logu.

**Historyczne dokumenty powyżej opisują starsze widoki:** wcześniejsze kontrastowe PNG 0°/90°, a następnie odtwarzacz 192 PNG z suwakiem Play/Pause. Oba zastępuje obecny GIF; nie należy ich ponownie implementować.
