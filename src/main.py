from brain.brain import AikaBrain

brain = AikaBrain()

print("AIKA Online")
print("Type 'exit' to quit")

while True:

    user_input = input("\nYou > ")

    if user_input.lower() == "exit":
        break

    try:
        response = brain.process(user_input)
    except Exception as e:
        print(f"\n[Error] {e}")
        continue

    print(f"\nAIKA > {response}")