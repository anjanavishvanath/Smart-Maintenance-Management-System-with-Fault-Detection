
def logic_test(baseline_exists):
    score = 0
    # z_score = 0  <-- variable in code
    # max_z is NOT initialized in code
    
    if baseline_exists:
        max_z = 10.0
        score = 2
    else:
        # Fallback
        score = 1
        
    # Later in code
    try:
        print(f"Max Z is {max_z}")
    except UnboundLocalError:
        print("Caught expected UnboundLocalError for max_z")
    except Exception as e:
        print(f"Caught unexpected error: {e}")

if __name__ == "__main__":
    print("Testing with baseline:")
    logic_test(True)
    print("\nTesting without baseline:")
    logic_test(False)
