#!/usr/bin/env python3
"""
Find the first 5 perfect numbers.
A perfect number equals the sum of its proper positive divisors (excluding itself).
"""

def get_divisors(n):
    """Get all proper divisors of n (excluding n itself)"""
    divisors = []
    for i in range(1, int(n**0.5) + 1):
        if n % i == 0:
            divisors.append(i)
            if i != n // i and n // i != n:
                divisors.append(n // i)
    # Remove n itself if it's in the list
    divisors = [d for d in divisors if d != n]
    return sorted(divisors)

def is_perfect(n):
    """Check if n is a perfect number"""
    divisors = get_divisors(n)
    return sum(divisors) == n

def find_perfect_numbers(count=5):
    """Find the first 'count' perfect numbers"""
    perfect_numbers = []
    n = 2  # Start from 2 (first perfect number is 6)

    print(f"Searching for the first {count} perfect numbers...\n")
    print("=" * 80)

    while len(perfect_numbers) < count:
        if is_perfect(n):
            divisors = get_divisors(n)
            divisor_sum = sum(divisors)

            perfect_numbers.append(n)

            print(f"\nPerfect Number #{len(perfect_numbers)}: {n:,}")
            print("-" * 80)
            print(f"Divisors: {', '.join(map(str, divisors))}")
            print(f"Sum of divisors: {' + '.join(map(str, divisors))} = {divisor_sum:,}")
            print(f"Verification: {divisor_sum:,} == {n:,} ✓")
            print("=" * 80)

        n += 1

        # For efficiency, use the Euclid-Euler theorem for larger perfect numbers
        # Perfect numbers have the form 2^(p-1) * (2^p - 1) where 2^p - 1 is prime
        if n > 10000:
            # Jump to candidates based on Mersenne primes
            # Known Mersenne prime exponents: 2, 3, 5, 7, 13, 17, 19, 31...
            primes = [2, 3, 5, 7, 13, 17, 19, 31, 61, 89, 107, 127]
            for p in primes:
                mersenne = (2 ** p) - 1
                candidate = (2 ** (p - 1)) * mersenne
                if candidate > n and candidate not in perfect_numbers:
                    # Verify it's actually perfect
                    if is_perfect(candidate):
                        divisors = get_divisors(candidate)
                        divisor_sum = sum(divisors)

                        perfect_numbers.append(candidate)

                        print(f"\nPerfect Number #{len(perfect_numbers)}: {candidate:,}")
                        print("-" * 80)
                        print(f"This number has {len(divisors)} divisors")
                        print(f"Sum of divisors: {divisor_sum:,}")
                        print(f"Verification: {divisor_sum:,} == {candidate:,} ✓")
                        print("=" * 80)

                        if len(perfect_numbers) >= count:
                            break
                    n = candidate
            break

    return perfect_numbers

if __name__ == "__main__":
    perfect_numbers = find_perfect_numbers(5)

    print("\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"\nThe first 5 perfect numbers are:")
    for i, num in enumerate(perfect_numbers, 1):
        print(f"  {i}. {num:,}")
    print()
