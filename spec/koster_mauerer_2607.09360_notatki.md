# Köster & Mauerer, arXiv:2607.09360: notatki dla projektu QEM

**Bibliografia.** D. Köster (OTH Regensburg), W. Mauerer (OTH Regensburg / Siemens AG), *Benchmarking Error Mitigation: Artefactual Improvements in Zero-Noise Extrapolation*, arXiv:2607.09360. v1: 10.07.2026; **przeczytano v2 z 03.08.2026**. Komentarz na arXiv: 4 strony z bibliografią, 2 rysunki, przyjęte na IEEE Quantum Week (QCE) 2026. Praca nie ma appendixów. Szczegóły (m.in. dokładna konstrukcja garbage folds oraz analiza Allana) autorzy odsyłają do „reproduction package” i archiwum Zenodo. Tych materiałów nie czytano.

## 1. Teza
Gdy wartości przy λ>1 spadają do „podłogi” obserwabli f, Richardson ZNE przestaje odzwierciedlać fizykę. Wynik staje się wtedy stałym przeskalowaniem jednego pomiaru E(λ₁). Pozorna poprawa nie zależy od metody wzmacniania szumu, a więc pojawia się nawet przy foldingu bezużytecznym. Autorzy nazywają to „horoscope effect”, przez analogię do Govia et al. dla PEC (Sec. I).

## 2. Mechanizm kolapsu (Sec. II–III, Eq. 1–2)
- Eq. (1): Ê(0)=Σ c_k E(λ_k), Σ c_k = 1, gdzie c_k to współczynniki Lagrange'a.
- Miara poprawy (Sec. II) to recovery ratio ρ=(Ê(0)−E(λ₁))/(E_ideal−E(λ₁)). ρ=0 oznacza brak poprawy, ρ=1 pełne odzyskanie wartości idealnej, a ρ>1 przestrzelenie, czyli overshoot niefizyczny.
- Wariancja: Var(Ê)=Σc_k² Var(E(λ_k)). Autorzy ograniczają czynnik wzmocnienia przez Σ|c_k|. Dla {1,3,5}: c=(15/8, −5/4, 3/8) i Σ|c|=3.5. Dla zbioru Kandali {1,1.1,1.25,1.5}: Σ|c|=681, czyli granica „194× większa” (Sec. II a).
- Podłoga f (Sec. II b): przy depolaryzacji obserwabla prawdopodobieństwa dąży do 1/2^N, a parzystość ⟨Z^⊗N⟩ do 0 (na sprzęcie może być nawet ujemna).
- **Eq. (2):** jeśli E(λ_k)≈f dla k>1, to Ê(0)=c₁E(λ₁)+(1−c₁)f. Dla {1,3,5} daje to **Ê(0)=15/8·E(λ₁) − 7/8·f**.
- Trzy wnioski: (1) wynik nie zależy od metody wzmacniania; (2) skoro c₁>1, każde E(λ₁) zostaje podbite w górę i możliwy jest overshoot; (3) poprawa pojawia się także przy niedziałającym wzmacnianiu. Mechanizm dotyczy **każdego liniowego ekstrapolatora z c₁>1**, nie tylko Richardsona na {1,3,5}.
- Sprzęt (Sec. III a, Fig. 1): 4-kubitowy Quantum Trotter Circuit (QTC), obserwabla ⟨Z^⊗4⟩ (f=0), folding na {1,3,5}, głębokość Trottera d=1,3,5. Przy d=1 sygnał zostaje zachowany (E(λ₃)=0.46) i Richardson odzyskuje wartość idealną. Przy d=3 i d=5 Ê(0) śledzi czyste przeskalowanie 15/8·E(λ₁) z dokładnością **do 5%**. Przy **d=3 overshoot wynosi 21% (Ê=1.16 przy E_ideal=0.96)**, a przy d=5 wynik „przypadkiem” ląduje poniżej ideału. Liczba ujemnych estymat per stan rośnie z **3/16 do 7/16**.

## 3. Taksonomia retencji sygnału (Sec. IV, Fig. 2)
Symulacja z szumem depolaryzującym p_2q=10⁻³ oraz dane z Euro-Q-Exa:
1. **Sygnał zachowany:** 6q QFT mirror ρ=0.99, 4q QTC ρ=1.00.
2. **Sygnał zdegradowany:** 6q Grover, E(λ₃)=0.078 i E(λ₅)=0.027 przy f=1/64, ρ=0.44.
3. **Sygnał zniszczony:** parzystość na Euro-Q-Exa jest ujemna przy λ=5, więc warunek Eq. (2) jest spełniony.

Taksonomia jest jakościowa. Praca nie podaje ilościowego progu („jak blisko f” to już kolaps).

## 4. Garbage folding jako kontrola negatywna (Sec. V)
- **Konstrukcja (Sec. V A):** fold wstawiony w miejsce U†U nie redukuje się do identyczności, tzn. U(U†U)≠U. Ma jednak tę samą liczbę bramek i to samo rezydualne tempo błędów co folding prawdziwy. Celem jest maksymalne zniszczenie sygnału przy λ>1, czyli dokładnie warunek Eq. (2). **Tekst nie podaje, jakie bramki składają się na garbage fold.** Szczegóły bramkowe są wyłącznie w pakiecie reprodukcyjnym.
- **Dopasowany koszt na sprzęcie (Sec. V D):** łańcuch kubitów 8–11, `optimization_level=0`, flaga `no_modify`. Wariant garbage i prawdziwy różnią się tylko wstawionymi kopiami foldów i mają **identyczną liczbę CZ przy każdym λ**.
- **Symulacja (Sec. V B):** na Groverze garbage daje ρ≈0.56, więcej niż genuine z ρ=0.44. Na QFT i QTC (sygnał zachowany) garbage daje ρ=16 i ρ=125. Autorzy wiążą to z ogólnym mechanizmem: jeśli rzeczywisty szum przy λ>1 jest silniejszy, niż zakłada model wielomianowy (efekty niemarkowowskie, błędy koherentne, większe błędy bramek), Richardson przeszacowuje.
- **Dwie odrębne drogi do niefizyczności (Sec. V C):**
  1. Ill-conditioning: rośnie Σ|c|. Na Groverze ρ_gen=0.44 przy {1,3,5} (Σ|c|=3.5), a przy zbiorze Kandali ρ_gen=6.0 (Σ|c|=681). Tu autorzy cytują granicę help–harm Scavino Alfaro [18].
  2. Zniszczenie sygnału: decyduje bliskość E(λ>1) do f, a nie Σ|c|, więc problem dotyka także {1,3,5}.
- **Sprzęt (Sec. V D):** IQM Euro-Q-Exa, 54 kubity, dostęp przez adapter MQSS Qiskit, LRZ Garching. 4096 shotów na obwód, błąd standardowy parzystości poniżej 0.02. Na tej kalibracji E(λ) wynosi 0.77, 0.41 i 0.12 dla λ=1, 3, 5, przy E_ideal=0.98. Średnia z **15 dopasowanych powtórzeń**:
  - genuine: ρ_gen=0.99±0.13;
  - **garbage: Ê_garb=1.38±0.04, ρ_garb=2.77±0.25**, a 10 z 16 estymat stanów bazowych jest ujemnych;
  - **identity fold** (dodatkowe pary natywnych bramek składające się do identyczności, w liczbie równej garbage foldingowi): ρ_id=0.74±0.09, bez overshootu i bez artefaktu.
  - Pomiar blokowy porównany z przeplatanym ogranicza bias między obwodami do <1.4×10⁻³. Odchylenie Allana skaluje się jak 1/√m, więc overshoot jest deterministyczny, a nie wynika z dryfu.
  - Tam, gdzie sygnał jest zachowany, genuine ZNE obniża MSE względem surowego λ=1 o ponad rząd wielkości.
- Niespójność widoczna w tekście: w Sec. V D genuine „lekko przestrzeliwuje”, choć ρ_gen=0.99±0.13 nie przekracza 1 w średniej. Do tego Fig. 2 pokazuje parzystość ujemną przy λ=5, a Sec. V D podaje E(λ₅)=0.12. To najpewniej inne kalibracje lub głębokości, ale praca tego nie precyzuje.

## 5. Kontrola zerokosztowa: ujemne prawdopodobieństwa (Sec. VI)
- Richardson stosuje się do każdego stanu bazowego osobno: P̂(s)=Σ_k c_k P_s(λ_k). Poprawny rozkład wymaga P̂(s)≥0. Małe naruszenia są normalne (c₂=−5/4 i szum shotów), duże wskazują na kolaps.
- Grover 6q przy p_2q=6.4×10⁻⁴: genuine ma 0/64 stanów ujemnych i min P̂=+0.0005; garbage ma 29/64 ujemnych i min P̂=−0.039.
- **W_neg=Σ_{s: P̂(s)<0}|P̂(s)|.** Wielkość ta nie wymaga ground truth i pozostaje ograniczona, w przeciwieństwie do ρ, który rozbiega się, gdy E_ideal→E(λ₁). Stąd biorą się ρ=16 i ρ=125.
- Sprzęt: **405 przebiegów = 45 powtórzeń × {genuine, identity, garbage} × {retained, decayed, destroyed}.** Foldingi poprawne (genuine, identity) mają W_neg=0.02–0.04, maksymalnie 0.06. Garbage ma 0.74±0.06, minimalnie 0.64. **AUC=1.0**, a współczynnik zmienności garbage jest poniżej 8% we wszystkich reżimach, bo W_neg nasyca się na suficie zależnym tylko od skal. Autorzy traktują W_neg jako binarną flagę ważności.
- Obcięcie wyniku do zakresu fizycznego (Miranskyy et al. [19]) nie wystarcza, bo artefakt może leżeć w tym zakresie (przypadek d=5).

## 6. Checklista raportowania (Sec. VII), pełna lista
1. Raportuj, czy E(λ) przy λ>1 zachowuje sygnał, czy osiągnęło podłogę obserwabli.
2. Raportuj per-stanowe W_neg obok Ê(0), a nie sam skalar.
3. Raportuj poprawę względem fizycznie osiągalnego maksimum i oznaczaj overshooty. Gdy ideał jest nieznany, ogranicz go klasycznie symulowalnym surogatem i oznacz każde Ê(0) powyżej tej granicy.

Niespełnienie któregokolwiek punktu oznacza artefakt. Do tego zalecana jest rutynowa kontrola negatywna garbage-folding z dopasowanym kosztem.

**Ograniczenia, które autorzy przyznają sami:** sprzęt to jedno urządzenie i jedna rodzina obwodów (QTC), a symulacja zakłada idealną depolaryzację. Próg wejścia w kolaps (głębokość, szum) zależy od urządzenia.

## 7. Mapowanie na nasz projekt (ODRA 5, Garnet)

**Współczynniki naszych węzłów** (policzone dokładnie; Eq. 2 w ogólnej postaci Ê=c₁E₁+(1−c₁)f):
- {1,3}: c₁=3/2, czyli Ê=1.5E₁−0.5f;
- {1,3,5}: c₁=15/8;
- {1,3,5,7}: c₁=35/16, czyli Ê=2.1875E₁−1.1875f;
- liniowy LSQ na {1,3,5}: c=(13/12, 1/3, −5/12), więc też c₁>1.

Wszystkie nasze ekstrapolatory liniowe podlegają zatem kolapsowi. Fit eksponencjalny jest nieliniowy i Eq. (2) go bezpośrednio nie obejmuje.

**Które liczby są zagrożone:**
- Punkt 39 CZ z kampanii twirlingowej na ODRA: |⟨O⟩(1)|=0.04, czyli sygnał już przy λ=1 leży na podłodze. Przy {1,3,5} λ=5 oznacza ok. 195 CZ. Wysoka retencja R=0.81/0.67 nie świadczy tu o sygnale, bo stosunek dwóch wielkości na podłodze to szum. Ten punkt jest **poza** reżimem, w którym Eq. (2) daje „ładną” poprawę: Ê to 15/8 razy szum. Każdy zysk ZNE w tym punkcie trzeba uznać za niebroniony, dopóki kontrole nie wypadną pozytywnie.
- Szczebel 54 CZ (zysk 1.27×; λ=3 to 162 CZ, λ=5 to 270 CZ) oraz szczebel 36 CZ: najbardziej prawdopodobny reżim „decayed/destroyed”. Zysk może pochodzić z czystego przeskalowania 15/8, tj. z tego, że |ideał| ≈ 1.875·|E₁|.
- 12 CZ (zysk 3.3×; λ=5 to 60 CZ): prawdopodobnie reżim retained, ale trzeba to sprawdzić tą samą procedurą.
- Walidacja κ (ścieżka 1, ill-conditioning i shoty) jest **ortogonalna** do ścieżki 2 (zniszczenie sygnału), co mówią sami autorzy w Sec. V C, cytując Scavino Alfaro [18]. Nasz „górny brzeg ZNE ograniczony przez garbage-folding” to dokładnie domknięcie ścieżki 2. Cytujemy obie prace jako komplementarne.
- Podłoga dla mean-Z: przy depolaryzacji f=0, ale na transmonach relaksacja T1 ściąga ⟨Z⟩ ku +1. Przy częściowo nieunitalnym szumie f>0 i wtedy Eq. (2) jest przesunięciem afinicznym. Twirling nie usuwa nieunitalności T1. Trzeba więc **zmierzyć f**, a nie zakładać f=0.
- Decyzje klasyfikatora: jeśli decyzja to sign(⟨O⟩) i f=0, czyste przeskalowanie 15/8 **nie może zmienić żadnej decyzji**. Zmniejsza wtedy błąd MSE i nie zmienia zgodności decyzji. Jeśli f≠0, przesunięcie −(7/8)f może odwracać decyzje w pobliżu progu. Stąd test: czy zmiany decyzji pod ZNE przy 36–54 CZ zgadzają się z przewidywaniem samej Eq. (2)?
- Nasz kod ZNE po cichu przełącza się na fit liniowy przy |EV|>1.25. To ukrywa overshooty i łamie punkt 3 checklisty. Fallback musi być logowany i raportowany.

**Kontrole zerokosztowe na istniejących danych** (o ile zapisaliśmy liczniki bitstringów per λ; tego tu nie zweryfikowano):
- (a) tracking test: |Ê − (c₁E₁+(1−c₁)f̂)| dla każdego punktu, z kryterium „≤5%” z Fig. 1 jako heurystyką;
- (b) W_neg i min P̂(s) na 32 stanach 5-kubitowych, a także na marginesach jednokubitowych;
- (c) ρ względem modelu bezszumowego (ideał jest dokładnie znany, bo 5 kubitów symulujemy klasycznie), z flagą ρ>1. Dla wejść z ideałem bliskim E₁ zamiast ρ używać W_neg.

Progi W_neg z pracy (0.06 / 0.64) dotyczą 16 stanów i 4096 shotów. Dla 32 stanów i naszej liczby shotów rozkład zerowy trzeba **skalibrować symulacją**.

**ODRA 5, sprzęt (nieograniczone kredyty):**
- Dla każdego szczebla 12/27/36/54 CZ i zamrożonego zbioru wejść uruchomić trzy warianty foldingu z identyczną liczbą i układem CZ przy każdym λ:
  - genuine: U(U†U)^k;
  - identity: pary natywnych bramek CZ·CZ i PRX(θ)PRX(−θ) na tych samych parach gwiazdy, w liczbie równej garbage;
  - garbage: np. U(V†U) albo U(V†V′), gdzie V i V′ mają ten sam szkielet CZ co U, ale losowe kąty PRX. Taki fold nie jest identycznością i ma ten sam koszt. To nasza konstrukcja, bo praca jej nie podaje.
- Ustawienia: stałe PHYS=[QB3,QB1,QB2,QB4,QB5], wyłączone optymalizacje i kasowanie par (odpowiednik `optimization_level=0` i `no_modify`; bariery), przypięta wersja Qiskit oraz `seed_transpiler`.
- Pomiar przeplatany wariantów i blokowy dla porównania, ok. 15–45 powtórzeń jak w pracy, z twirlingiem i bez.
- Podłogę f̂ mierzymy z obwodu garbage przy λ=5 lub z losowego obwodu o tej samej liczbie CZ.
- Kryterium publikacyjne: zysk ZNE uznajemy na danym szczeblu tylko wtedy, gdy genuine jest lepszy od garbage i identity, W_neg pozostaje w rozkładzie zerowym, a ρ≤1.

**Symulacja (Aer, środowisko `qem`):**
- (i) Czysta depolaryzacja, w której Richardson jest dokładny. Służy jako odniesienie i do kalibracji rozkładu zerowego W_neg przy naszych shotach.
- (ii) Model skalibrowany na ODRA z T1/T2, błędem CZ i readoutem, żeby przewidzieć, przy jakim CZ zaczyna się kolaps i jakie jest f dla mean-Z.
- (iii) Te same trzy warianty foldingu, a w efekcie mapa reżimów retained/decayed/destroyed na drabinie CZ, do porównania z ODRA przed kampanią.
