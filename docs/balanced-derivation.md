# Algebraic balanced-source target

Codex derivation for the owner-approved successor experiment. The source has
conditional field H=-a(r1+r2)+b*r1*r2. For return inputs, the two blocking
magnitudes are b (one bank) and 2a-b (both banks). At fixed a>0:

    min(b,2a-b) <= a,

with equality precisely at b=a. This is a maximum-minimum margin statement,
not a claim that equal margins optimize total stochastic errors when the two
input conditions have different frequencies and dynamics.

At dimensionless beta=1 the retained pair rows have microscopic strength 4:

    a = (1/2) log cosh(8).

Give the four triple-module rows and their hidden fields common strength t:

    b(t) = (1/2) log[cosh(2t)^4 / cosh(4t)].

This also permits a closed-form specification of the target used by the
numerical bisection in the native source builder. Set C=cosh(8), z=cosh(2t)^2.
Since cosh(4t)=2z-1, the equation b(t)=a becomes

    z^2 = C(2z-1),
    z = C + sqrt(C^2-C),
    t = (1/2) acosh(sqrt(C + sqrt(C^2-C))).

The other quadratic root is below 1 and cannot be cosh(2t)^2 for real t.
Thus the positive strength is specified by the source equations, independently
of seeds or observed event errors. The native numerical construction returns
2.3464897298984759, with a=b=3.6534264659876117 in its binary64 output.

At arbitrary beta>0, equalization would require

    C(beta)=cosh(8 beta),
    t(beta)=acosh(sqrt(C(beta)+sqrt(C(beta)^2-C(beta))))/(2 beta).

A single fixed t chosen at beta=1 is therefore distinct from the earlier
all-temperature ratio-locking construction based on two coupling scales.
The present experiment changes source strengths at fixed beta, retains the
six-hidden-spin topology, and tests the resulting full finite-rate dynamics.
