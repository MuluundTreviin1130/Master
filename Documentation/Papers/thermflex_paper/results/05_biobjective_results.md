# Biobjective Results

## Purpose

This block captures the role of the biobjective thermflex optimization path.

Primary raw source:

- [biobj_gold_candidates_20260403_093146](/c:/Users/Philipp%20Thunshirn/Desktop/PhD/Python%20model/Master/Optimization/run/results/Vienna/gold/biobj_gold_candidates_20260403_093146)

## Current Role in the Paper

The biobjective path is not the main thermflex proof. It is a structured
extension inside the thermflex analysis.

It contributes:

- a cost end-point
- a CO2 end-point
- a mid-tradeoff point

Current selected representatives:

- `biobj_cost_end`
- `biobj_co2_end`
- `biobj_mid_tradeoff`

## Interpretation

This block is useful if the paper wants to show that:

- once thermflex is admitted as an operational degree of freedom,
- the choice of policy/design point is not one-dimensional,
- and cost vs CO2 trade-offs remain relevant even within the thermflex-enabled
  space

## Immediate Paper Use

Treat this as:

- an optional main-text extension
- or an appendix/result supplement

It should not displace the simpler and stronger main narrative built from:

- isolated thermflex comparison
- representative-day dependence
- cohort mechanism
