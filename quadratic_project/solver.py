#!/usr/bin/env python3
"""
quadratic_project/solver.py

A small utility for solving quadratic equations of the form:

    ax² + bx + c = 0

The module provides:
* `solve_quadratic(a, b, c)` – returns a tuple with the two roots
  (real or complex, depending on the discriminant).
* A command‑line interface that accepts the coefficients as arguments
  and prints the resulting roots.

The implementation follows standard Python conventions (PEP 8) and
includes basic validation and error handling.
"""

from __future__ import annotations

import argparse
import cmath
from typing import Tuple, Union

Number = Union[int, float, complex]


def solve_quadratic(a: Number, b: Number, c: Number) -> Tuple[Number, Number]:
    """Solve the quadratic equation ax² + bx + c = 0.

    Parameters
    ----------
    a : Number
        Coefficient of x². Must be non‑zero.
    b : Number
        Coefficient of x.
    c : Number
        Constant term.

    Returns
    -------
    Tuple[Number, Number]
        A tuple containing the two roots (root1, root2). The roots are
        returned as ``float`` when they are real numbers and as ``complex``
        when the discriminant is negative.

    Raises
    ------
    ValueError
        If ``a`` is zero (the equation is not quadratic) or if any of the
        coefficients cannot be interpreted as a numeric type.
    """
    # Validate that the coefficients are numeric
    try:
        a = float(a)
        b = float(b)
        c = float(c)
    except (TypeError, ValueError) as exc:
        raise ValueError("All coefficients must be numeric values.") from exc

    if a == 0:
        raise ValueError("Coefficient 'a' must be non‑zero for a quadratic equation.")

    # Compute discriminant using cmath to automatically handle complex results
    discriminant = cmath.sqrt(b * b - 4 * a * c)

    # Two roots using the quadratic formula
    root1 = (-b + discriminant) / (2 * a)
    root2 = (-b - discriminant) / (2 * a)

    # If the imaginary part is negligible, return a real float for nicer output
    def _real_if_possible(z: complex) -> Number:
        if isinstance(z, complex) and abs(z.imag) < 1e-12:
            return z.real
        return z

    return _real_if_possible(root1), _real_if_possible(root2)


def _parse_args() -> argparse.Namespace:
    """Parse command‑line arguments."""
    parser = argparse.ArgumentParser(
        description="Solve a quadratic equation ax² + bx + c = 0."
    )
    parser.add_argument(
        "a",
        type=float,
        help="Coefficient a (must be non‑zero).",
    )
    parser.add_argument(
        "b",
        type=float,
        help="Coefficient b.",
    )
    parser.add_argument(
        "c",
        type=float,
        help="Coefficient c.",
    )
    return parser.parse_args()


def _format_root(root: Number) -> str:
    """Return a nicely formatted string for a root."""
    if isinstance(root, complex):
        return f"{root.real:.6f} {'+' if root.imag >= 0 else '-'} {abs(root.imag):.6f}j"
    return f"{root:.6f}"


def main() -> None:
    """Entry point for the command‑line interface."""
    args = _parse_args()
    try:
        root1, root2 = solve_quadratic(args.a, args.b, args.c)
    except ValueError as err:
        print(f"Error: {err}")
        return

    print("Roots of the equation:")
    print(f"  x₁ = {_format_root(root1)}")
    print(f"  x₂ = {_format_root(root2)}")


if __name__ == "__main__":
    main()
