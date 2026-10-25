# PCB — mapy gęstości prądu na miedzi (pierwszy tor diagnostyczny)

**Stan:** kod zapisu, odczytu, raportowania i testy offline dodane. **Nie uruchomiono natywnej symulacji openEMS na Windows użytkownika, więc nie ma jeszcze zweryfikowanych map dla `stripline4.epro`.** Ani testy syntetyczne, ani możliwość wyrysowania PNG nie stanowią walidacji fizycznej. Funkcja jest opt-in, domyślnie wyłączona, bez zmian solvera antenowego.

## Konkretny przypadek: gerbs/stripline4/stripline4.epro

Archiwum ZIP zawiera fizyczny stos **TOP / Inner1 / Inner2 / BOTTOM**, trzy dielektryki 361 / 362 / 363, pięć nazwanych sieci `TX`, `GND`, `+5V`, `3V`, `1V`, osiem komponentów i dziesięć rekordów VIA. W `LAYER_PHYS` pola fizycznej przenikalności dielektryków są niezdefiniowane/zerowe — to nie znaczy εr=0. Do symulacji trzeba wpisać **świadomie wybrane wartości εr oraz tanδ**, odpowiednie dla materiału i interesującej częstotliwości. Jeżeli metalizacja PTH nie wynika jednoznacznie z CAD, dotychczasowy preflight wymaga jej podania. Nie uzupełniać materiałów ani galwanizacji domyślną wartością.

## Jak uzyskać pierwszą mapę na Windows 11

1. `git pull --ff-only`; uruchom aplikację `PCB_GUI.bat`.
2. Wybierz `gerbs/stripline4/stripline4.epro`. Użyj istniejącego `Inspekcja`, aby potwierdzić aktywną płytkę, miedź, komponenty i źródło.
3. W zakładce materiałów EM przypisz do trzech warstw dielektryka własne εr i tanδ; uzupełnij PTH plating, jeżeli zgłosi go preflight. Nie wpisuj fikcyjnych danych tylko po to, żeby symulacja ruszyła.
4. W ustawieniach eksperymentu wybierz pasmo pobudzenia i częstotliwość mapy w polu **Pola przy**. Zaznacz `Zapisz pola E i H` oraz **`Mapa prądu na wszystkich warstwach miedzi (rot H; wynik eksperymentalny)`**. Częstotliwości muszą mieścić się w zadanym sweep i paśmie skutecznego pobudzenia.
5. Uruchom **PREPARE-ONLY**, obejrzyj liczbę komórek, zakres dumpów, pozycje warstw, informacje o materiałach i porcie. Żadna część przygotowania nie uruchamia FDTD.
6. Dopiero gdy przygotowanie przejdzie bez błędu, uruchom FDTD w GUI. Po rzeczywistym zapisie widm i zakończeniu procesu otwórz automatyczny raport HTML lub użyj zakładki Raport. Sekcja **Gęstość prądu na miedzi — mapa diagnostyczna** zawiera osobne widoki warstw i częstotliwości, wspólną skalę |K| oraz strzałki chwilowego wektora w fazach 0°/90°.
7. Gdy obliczenie się przerwie, skorzystaj z dotychczasowego `postprocess` (w osobnym katalogu) dla odzyskania **faktycznie istniejących** HDF5. Pusty `FieldData/FD` daje status `failed` i przyczynę, nie udawaną zerową gęstość prądu.

Opcjonalny CLI to dotychczasowe `python -m antenna_lab.pcb.easyeda_control` z przełącznikiem `--surface-current` **razem z** `--fields-mhz` i kompletnymi parametrami modelu; tryby `--prepare-only` / `--yes` pozostają bez zmian. Zapis prądu nie jest włączony w dawnych przebiegach ani w antenowym solverze Quados/biquad.

## Co dokładnie jest liczone

- Dla każdej obsadzonej warstwy miedzi kod dodaje jeden natywny dump openEMS `dump_type=13`, `dump_mode=1`, `file_type=1`. To **częstotliwościowa gęstość prądu całkowitego `rot(H)` [A/m²]**, a nie natywnie bezpośredni powierzchniowy K.
- Pozycja Z dumpu jest dokładnie istniejącą linią siatki w miejscu modelowanego sheetu; brak zgodności powoduje błąd, bez przesuwania płaszczyzny. Brak limitu czterech warstw. `MAX_FIELD_POINTS` ogranicza sumę pozycji/częstotliwości dla ochrony pamięci; użytkownik zmienia parametry jawnie.
- Postprocessing wyznacza **estymatę** `K_est = rot(H)_t * dual_width_z` w [A/m], gdzie `dual_width_z = (z[k+1] - z[k-1])/2`. To metoda podobna do wykorzystanej w [Fairbeam](https://github.com/ismailakdag/fairbeam/blob/main/python/fairbeam/fields.py), lecz w przeciwieństwie do Fairbeam zachowuje nieznormalizowane zespolone składowe i deklarowaną jednostkę estymaty. **Dokładność absolutna nie jest jeszcze potwierdzona.**
- Pełne `native/pcb_curlH_XXX.h5` pozostają nienaruszone; `currents/pcb_curlH_XXX.npz` zawiera fazory, skalowanie do 1 V portu, rzeczywistą siatkę, `on_copper` i dual-width. `currents/metadata.json` przechowuje pochodzenie, status i ograniczenia. Maska odcina tylko obszar poza fizyczną geometrią miedzi; *nie* odcina otoczenia metalu na przekątnej komórki, jak stara E/H.
- Wspólna skala map obejmuje wszystkie warstwy i częstotliwości w jednym raporcie; użytkownik może uczciwie porównać koncentrację prądu. Max jednej krawędzi zależy od idealizacji i rozdzielczości.

## Czego wynik NIE oznacza

Nie jest to jeszcze zweryfikowane `K_net = n × (H_plus − H_minus)`, ani osobne K górnej i dolnej fizycznej powierzchni folii 35 µm, ani objętościowy rozkład `J` przez miedź. Nie pozwala bez osobnej walidacji obliczyć strat AC, skin effect, ilościowych pików na ostrych narożach czy rozkładu ładunku `rho_s`. Materiał typu conducting sheet oraz lokalne porty/via wymagają szczególnej oceny. Brak ręcznych danych εr/tanδ, metalizacji lub nieskuteczne wzbudzenie oznacza brak wiarygodnej symulacji, niezależnie od jakości mapy. Obecny model portu i normalizacja 1 V mają status `unverified`.

**Warunek odbioru kolejnego etapu:** użytkownik otwiera raport z natywnego FDTD dla `stripline4` i stwierdza, czy prąd płynie po spodziewanych sieciach, czy cztery warstwy są rozdzielone, czy faza i skala są użyteczne. Następnie porównujemy wyniki na zagęszczonej siatce i metodą granicznych skoków H. Dopiero po takim odbiorze wolno nazywać K wynikami ilościowymi i przejść do ładunku/pól jednostronnych. Gdy dump nie daje użytecznej wartości — zatrzymujemy tę gałąź, zachowujemy dane i wybieramy metodę alternatywną, zamiast rysować fikcyjne prądy.

Źródła: [openEMS: dump_type/dump_mode](https://docs.openems.de/en/latest/python/CSXCAD/CSProperties/CSPropDumpBox.html), [openEMS: HDF5 / siatka](https://docs.openems.de/en/latest/concepts/dump_hdf5.html), [Fairbeam](https://fairbeam.org/docs/bundle.html), [wymaganie docelowe](pcb-current-charge-goal.md).

## Stripline4_004 — prawdziwy przebieg i widoki z kontrastem

Użytkownik przeprowadził 48488 kroków FDTD w 5282,8 s, a openEMS wypisał: `RunFDTD: end-criteria of -40.00dB reached ... (-41.29dB)`. Raport potwierdza pełną ścieżkę danych `currents: processed` dla czterech warstw × 1 i 2 GHz. Jednocześnie `openEMS_stats.txt` nie został znaleziony, dlatego formalny status ukończenia czasowego pozostaje `unconfirmed` mimo informacji w konsoli. Ilościowa dokładność K pozostaje `unverified`.

**Ważne:** dla dielektryków 361/362/363 wpisano εr=4 i **tanδ=1.001**, nie 0.001. To ekstremalnie stratny model w porównaniu z typowym laminatem PCB — trzeba to potwierdzić z kartą materiałową przed nowym kosztownym solve. Grubości miedzi wewnętrznej pokazane w raporcie to ~350 µm, zewnętrznej ~35 µm; obecna miedź PEC ignoruje te grubości.

Dotychczasowe mapy używają wspólnej skali liniowej ~450 A/m/1 V, przez co słabsze struktury są niemal niewidoczne. Raport ma teraz **dodatkową podsekcję „Kontrast lokalny”** dla każdej warstwy i f: logarytmiczną skalę ograniczoną percentilem 99,5 dodatnich wartości, jawne realne maksimum i liczbę pikseli o nasyconym kolorze. To wyłącznie transformacja WIZUALIZACJI, nie danych K i nie nowa analiza fizyczna. **Dla porównań ilościowych nadal używać mapy z globalną skalą!** W GUI otworzyć zakładkę **Raport** dla już istniejącego `outcomes/pcb_easyeda/stripline4_004` i wygenerować widok ponownie. Nie uruchamiać powtórnie FDTD. Obecne NPZ/HDF5 pozostają niezmienione. Dodano test kodu, niewykonany jeszcze na Windows.

