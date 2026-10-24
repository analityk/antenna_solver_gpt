# Pola E/H — stan i nowy cel

Aktualny tor PCB zapisuje trzy przestrzenne przekroje `xy_air`, `xz_feed`, `yz_feed`, zespolone E/H na istniejącej siatce, normalizowane do 1 V portu. Używa `dump_mode=1`, interpolacji do węzłów, geometrycznej maski miedzi/halo i raportu z fazami. Kadrowanie `active+geometry` z marginesem 1 mm jest wyłącznie ustawieniem prezentacji, nie pomiarem 1 mm od metalu.

**Nowy, niezaimplementowany tryb**: `copper-faces`, E/H po obu stronach każdej fizycznej warstwy miedzi, N warstw = 2N widoków XY. Musi zapisywać stronę, pozycję z, ośrodek, częstotliwości, normalizację, siatkę, maskę i wiarygodność. Nie można zastosować obecnej maski halo bez zmian; węzeł interpolowany przez PEC nie gwarantuje poprawnego pola granicznego. Obecny zerogrubościowy model nie rozdziela prądów obu fizycznych powierzchni folii. K netto jest ewentualnym wynikiem po walidacji, a nie zamiennikiem wymaganych E/H.

Szczegółowe wymagania i testy: [pcb-copper-surfaces.md](pcb-copper-surfaces.md). Stary tor E/H ma pozostać dostępny i kompatybilny. Nie uruchamiano nowych testów/FDTD przy tej aktualizacji.
