# Baseline Error Suppression and Mitigation

Before applying complex post-processing techniques like Zero-Noise Extrapolation (ZNE), the quantum circuit must be optimized at the execution level to suppress decoherence and correct classical measurement faults. This is achieved through Dynamical Decoupling (DD) and Readout Error Mitigation (REM). 

## Dynamical Decoupling (DD)

To truly grasp how DD works without the complex math, imagine a group of runners on a track. They represent a quantum state in superposition. Ideally, they should all run at the exact same speed. However, the track is uneven (representing environmental noise and local magnetic field fluctuations). Because of this noise, some runners speed up while others slow down. Over time, the pack spreads out and loses its tight formation‚Äîthis is exactly what happens during quantum dephasing (loss of coherence).

Now, imagine a referee blows a whistle exactly halfway through the race (this is our $\pi$-pulse). Upon hearing the whistle, every runner instantly turns around 180 degrees and runs back toward the starting line at their exact previous speed. The faster runners now have further to run back, while the slower ones have a shorter distance. The result? They all arrive at the starting line at the exact same moment, perfectly back in formation. 

Dynamical Decoupling simply repeats this "turnaround" process rapidly. By constantly flipping the state, any error introduced by the environment is immediately "unwound" or reversed before it has a chance to permanently ruin the quantum information.

Dynamical Decoupling is an open-loop quantum control technique designed to suppress idle-qubit decoherence (such as $T_1$ relaxation and $T_2$ dephasing) caused by system-environment interactions. In the context of topology-aware compilation, SWAP gates introduce significant circuit depth, leaving non-participating qubits idle for extended periods. 

Let the total Hamiltonian of the system and environment be defined as:
$$H = H_S \otimes I_E + I_S \otimes H_E + H_{int}$$
where $H_S$ and $H_E$ are the system and environment Hamiltonians, respectively, and $H_{int}$ is the interaction Hamiltonian causing decoherence. 

DD introduces a time-dependent control Hamiltonian $H_c(t)$ consisting of a sequence of instantaneous, equidistant unitary pulses (typically $\pi$-pulses like the Pauli $X$ and $Y$ gates). Over a total idle time $T$, a sequence of $N$ pulses $\{P_k\}_{k=1}^N$ is applied at intervals $	au$. The total time evolution operator becomes:
$$U(T) = \prod_{k=1}^{N} \left( P_k e^{-i H 	au} 
ight)$$

By carefully choosing the pulse sequence (e.g., Hahn Echo, CPMG, or XY4), the average effect of the interaction Hamiltonian is dynamically averaged to zero up to the first order in the Magnus expansion:
$$ \overline{H}_{int}^{(0)} =  rac{1}{T} \sum_{k=1}^{N} P_k^\dagger H_{int} P_k  pprox 0 $$
This effectively decouples the idle qubits from the environment, ensuring the quantum state remains coherent while waiting for distant SWAP operations to complete.

The XY4 sequence is a robust DD protocol consisting of four $\pi$-pulses applied alternately along the X and Y axes of the Bloch sphere: $	au - X - 2	au - Y - 2	au - X - 2	au - Y - 	au$.

The process of automatically inserting DD into a quantum circuit by a compiler requires treating the circuit as a continuous time schedule rather than just a sequence of logical gates:

1. **DAG Transformation:** The compiler converts the circuit into a Directed Acyclic Graph (DAG) to determine logical execution order, and maps it to the physical hardware topology (inserting SWAPs).
2. **Hardware Calibration Retrieval:** The compiler fetches the latest backend properties, extracting exact physical execution times (in nanoseconds) and the hardware clock resolution ($dt$) for every specific gate.
3. **Scheduling (ALAP/ASAP):** The compiler assigns absolute $t_{start}$ and $t_{end}$ timestamps to every gate. *As Late As Possible* (ALAP) is typically used to delay initialization and minimize the time qubits spend in vulnerable superposition.
4. **Idle Window Extraction:** The compiler scans the timeline of each physical qubit, identifying gaps where $t_{start}$ of the next gate is greater than $t_{end}$ of the previous gate. This difference defines the idle time $T_{idle}$.
5. **Pulse Padding:** Once a sequence (like XY4) is selected, the compiler subtracts the duration of the physical microwave pulses from $T_{idle}$. The remaining time is mathematically divided into equal passive intervals ($	au$) that perfectly align with the hardware's digital clock grid.
6. **Pulse Injection:** The passive gaps in the DAG are replaced with concrete microwave pulse schedules (e.g., DRAG envelopes), transforming the idle time into active, rhythmic protection against decoherence.

## Readout Error Mitigation (REM)

While Dynamical Decoupling (DD) operates at the hardware level during circuit execution to protect against decoherence, Readout Error Mitigation (REM) is a classical post-processing technique applied after the circuit has finished running. In superconducting qubits, measurement fidelity is fundamentally limited by readout mechanisms (e.g., microwave resonators) and thermal noise. This results in State Preparation and Measurement (SPAM) errors, where the hardware misclassifies the final quantum state (e.g., recording a 1 when the qubit was actually in state 0).

Imagine an automated sorting machine on a farm that separates oranges (state $|0
angle$) and grapefruits (state $|1
angle$). The optical sensor is flawed:
* When an orange passes, it correctly identifies it 90% of the time, but misclassifies it as a grapefruit 10% of the time.
* When a grapefruit passes, it correctly identifies it 95% of the time, and misclassifies it as an orange 5% of the time.

If the machine sorts 1,000 fruits and reports 500 of each, we know this data is skewed. However, because we know the exact error rates of the sensor, we do not need to physically re-sort the fruits. We can simply use linear algebra to calculate backward and deduce the true, original number of oranges and grapefruits. This is the essence of classical REM.

Measurement errors act as a classical Markov process on the ideal probability distribution. We characterize this noise by constructing a **Calibration Matrix** (or Assignment Matrix) $A$. For an $n$-qubit system, this matrix has a size of $2^n 	imes 2^n$. The elements are defined by the conditional probabilities:
$$ A_{i|j} = P(	ext{measure state } i \mid 	ext{prepare ideal state } j) $$

When the hardware measures the state, nature physically multiplies the true probability distribution ($ ec{p}_{ideal}$) by this noise matrix, yielding a noisy output:
$$  ec{p}_{noisy} = A  ec{p}_{ideal} $$

Mathematically, recovering the ideal distribution seems straightforward‚Äîjust multiply the noisy results by the inverse of the calibration matrix:
$$  ec{p}_{mit} = A^{-1}  ec{p}_{noisy} $$

However, in practical laboratory settings, this exact inversion approach frequently fails. Because quantum processors return statistics from a finite number of shots (e.g., 1024 shots), the vector $ ec{p}_{noisy}$ contains statistical shot noise. Multiplying a statistically imperfect vector by $A^{-1}$ often produces non-physical results, such as negative probabilities (e.g., $P(|0000
angle) = -0.04$) or probabilities that sum to greater than 1. This will crash classical optimizers in algorithms like VQC.

Instead of naive matrix inversion, modern compilers use classical optimization solvers (like SLSQP). We formulate the mitigation as a constrained optimization problem. We ask the solver to find an ideal vector $ ec{x}$ that minimizes the distance to the measured data:
$$ \min_{ ec{x}} || A ec{x} -  ec{p}_{noisy} ||^2 $$
subject to strict physical constraints:
1. $x_i \geq 0$ for all $i$ (no negative probabilities).
2. $\sum x_i = 1$ (probabilities must sum to 1).

To successfully deploy REM in a hybrid algorithm like VQC, it is integrated into a multi-step pipeline:

1. **Hardware Characterization:** Before running the main algorithm, the compiler executes calibration circuits (preparing and measuring known computational basis states) on the active qubits to build the $A$ matrix.
2. **VQC Execution:** The main algorithm runs, producing the skewed measurement data ($ ec{p}_{noisy}$).
3. **Classical Post-Processing (REM):** The classical computer applies the Constrained Least Squares solver to mitigate the readout errors, generating the physical $ ec{p}_{mit}$.
4. **Synergy with ZNE:** When calculating the expectation value of an observable $O$, the formula becomes $\langle O 
angle_{mit} =  ec{O}^T  ec{p}_{mit}$. Feeding readout-error-free expectation values into higher-level error mitigation protocols, such as Zero-Noise Extrapolation (ZNE), is crucial. It allows ZNE to focus exclusively on mitigating depolarizing gate noise (e.g., from SWAP gates) without being confused by classical measurement bias.

---

# Concepts and Mathematical Framework

To quantify the effectiveness of our mitigation, we focus on the expected (average-case) square deviation of our estimator $\hat{O}$ from the true value $Tr[O
ho_0]$, which is called the mean square error (MSE):
$$MSE[\hat{O}] = E[(\hat{O} - Tr[O
ho_0])^2]$$

The ultimate goal of error mitigation is to reduce $MSE[\hat{O}]$ as much as possible using only finite resources. In the limit of a large number of circuit executions, the mean square error $MSE[\overline{O}_{
ho}]$ will be mainly limited by the bias of the estimator $Bias[\overline{O}_{
ho}]$, which is a systematic error that cannot be reduced by increasing the number of circuit runs. 

In order to reduce the bias, we construct an error-mitigated estimator $O_{em}$ using the same number of circuit runs $N_{cir}$. We want to construct $O_{em}$ such that it achieves a smaller bias than the naive noisy estimator $O_{
ho}$, meaning $|Bias[O_{em}]| \leq |Bias[O_{
ho}]|$. However, this reduction in bias usually requires constructing a more complex estimator that amplifies useful information, resulting in an increased variance. The sampling overhead required to reach the same shot noise level as the original noisy estimator is given by:
$$C_{em} =  rac{Var[\hat{O}_{em}]}{Var[\hat{O}_{
ho}]}$$

## Zero-Noise Extrapolation (ZNE)

Zero-Noise Extrapolation utilizes noisy states obtained at different circuit fault rates, denoted as $\lambda$. The noisy state obtained at fault rate $\lambda$ is $
ho_{\lambda}$, and the noisy expectation value $Tr[O
ho_{\lambda}]$ can be viewed as a function of $\lambda$. 

Using $\lambda_{1}$ to denote the smallest circuit fault rate we can achieve, we probe $Tr[O
ho_{\lambda}]$ at a range of boosted error rates $\{\lambda_{m}\}$ with $\lambda_{m} < \lambda_{m+1}$ to obtain a set of data points $\{(\lambda_{m}, Tr[O
ho_{\lambda_{m}}])\}$. 

For Richardson extrapolation, which assumes $Tr[O
ho_{\lambda}]$ can be approximated using a polynomial function, the error-mitigated estimate of the zero-noise output $Tr[O
ho_{0}]$ is:
$$E[\hat{O}_{em}] = 	heta_{0}^{*} = \sum_{m=1}^{M} Tr[O
ho_{\lambda_{m}}] \prod_{k 
eq m}  rac{\lambda_{k}}{\lambda_{k} - \lambda_{m}}$$

The error-mitigated expectation value is a linear combination of the set of noisy expectation values, meaning it can be estimated using Monte Carlo sampling. The corresponding sampling overhead for Richardson extrapolation is bounded by:
$$C_{em} \sim \left( \sum_{m=1}^{M} \left| \prod_{k 
eq m}  rac{\lambda_{k}}{\lambda_{k} - \lambda_{m}} 
ight| 
ight)^2$$

* If any Probed circuit fault rate $\lambda_{m}$ is too big or the gap between data points $|\lambda_{m} - \lambda_{k}|$ is too small, $C_{em}$ blows up and extrapolation becomes infeasible.
* For exponential scaling (which handles large $\lambda$ better than polynomial extrapolation), an exponential decay curve $f(\lambda;  ec{	heta})$ is fitted to the data.