# Deep research — łączenie metod QEM + nowe idee (2026-08-26)

Notatka z web-researchu: gdzie nasze podejście (twirling + CDR/ZNE) siedzi w literaturze,
co jest nowe, i jakie inne idee warto rozważyć.

## 1. Łączenie metod QEM — stan wiedzy

**RC + ZNE (dokładnie nasza kompozycja) — USTALONE:**
- *Synergetic QEM by randomized compiling + ZNE for VQE* (Quantum 2023, arXiv:2212.11198): RC
  zamienia koherentny→stochastyczny, co **waliduje założenie stochastyczne, którego ZNE
  potrzebuje** → poprawa energii nawet o **2 rzędy wielkości** przy szumie koherentnym. Kluczowy
  cytat: *„RC to wartościowy KOMPONENT PRZYGOTOWAWCZY wielu schematów EM, bo waliduje założenie
  stochastycznych błędów wymagane dla LINIOWEJ (a nie kwadratowej) ekstrapolacji."*
- *RC + Grover na jonach uwięzionych* (arXiv:2503.05344): supresja koherentna przez RC.

**CDR + ZNE:** vnCDR (variable-noise CDR) — łączy ZNE i CDR, lepsze wyniki.

**PEC + ZNE:** NEPEC (noise-extended PEC, arXiv:2108.02237) — ogólny framework obejmujący PEC i ZNE
jako przypadki graniczne.

## 2. Gdzie SIEDZIMY i co jest NOWE u nas

Nasz twirl+CDR to instancja „RC jako komponent przygotowawczy" — **mechanizm potwierdzony w
literaturze** (to dobrze: nie wymyślamy koła, stoimy na ugruntowanym). NASZE nowe kąty:

1. **Oś KOSZTU ROUTINGU / topologii.** Literatura RC+ZNE robi to na ustalonych obwodach (VQE);
   my pokazujemy **jak kompozycja załamuje się z narzutem routingu, rozdzielone po topologii**.
   To wygląda na lukę — search nie znalazł bezpośredniego konkurenta dla „gdzie QEM przestaje się
   opłacać pod routingiem, cross-topology". **Nasz Core Value jest realnie nowy.**
2. **CDR > ZNE pod twirlingiem** (nasz H4): CDR (fit liniowy) jest BARDZIEJ wrażliwe na koherencję
   niż ZNE (ekstrapolacja) → twirl pomaga CDR bardziej. Literatura RC+ZNE tego niuansu nie
   podkreśla — my go izolujemy i pokazujemy na sprzęcie.
3. **Kwantyfikacja frakcji koherentnej** (URB+RB) i pokazanie, że na Garnet jest MAŁA i drift-swamped
   → zysk RC modest i na poziomie OBWODU. To „predicted==measured" w kontekście routingu.

## 3. Inne idee QEM (świeże, do rozważenia)

- **ML-based QEM** (arXiv:2501.04558 physics-inspired NN; graph-NN mapujące łączność sprzętu na graf
  skierowany z profilem szumu native-gate; 2-design training zamiast losowego Clifforda). **Graf-NN
  kodujący topologię** jest szczególnie ciekawy dla naszego kąta topologicznego — ale to duży,
  osobny kierunek (dataset-heavy).
- **Light-cone-aware estimators** (redukcja sampling overhead dla obserwabli lokalnych o rzędy
  wielkości) — bezpośrednio dotyczy naszej osi shots-to-target.
- **Partial error correction / „almost fault-tolerant"** — nie trzeba korygować wszystkiego;
  łączy się z naszą detekcją [[4,2,2]] (QEC-lite).
- **Noise-estimation circuits** dla depolaryzacji (arXiv:2103.08591) — pokrewne URB/koherencji.
- **Best practices for digital ZNE** (arXiv:2307.05203) — do zacytowania przy naszym ZNE.

## 4. Wnioski dla naszego paperu

- **Zacytować** synergetic RC+ZNE (2212.11198), vnCDR, NEPEC, best-practices-ZNE (2307.05203) —
  osadza naszą kompozycję w literaturze.
- **Podkreślić nowość:** oś routingu/topologii + CDR>ZNE niuans + kwantyfikacja koherencji (URB).
  Framing: *„RC jako komponent przygotowawczy — GDZIE i DLA KTÓREJ METODY opłaca się pod narzutem
  routingu, rozstrzygnięte przez zmierzoną frakcję koherentną."*
- **Przyszłe kierunki (discussion):** graph-NN QEM świadome topologii; light-cone estimators dla
  cost-axis; partial-EC most między naszą detekcją a mitygacją.

## Źródła
- Synergetic RC+ZNE: arXiv:2212.11198 (Quantum 2023)
- vnCDR / data-driven EM: arXiv:2011.01157 (unified), Czarnik CDR 2005.10189
- NEPEC (PEC+ZNE): arXiv:2108.02237
- RC+Grover (ions): arXiv:2503.05344
- Best practices ZNE: arXiv:2307.05203
- ML QEM: arXiv:2501.04558, 2309.17368 (practical ML-QEM)
- Noise-estimation circuits: arXiv:2103.08591
