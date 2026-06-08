from brain.brain import AikaBrain

brain = AikaBrain()

print("AIKA Online")
print("Type 'exit' to quit")

while True:

    user_input = input("\nYou > ")

    if user_input.lower() == "exit":
        break

    response = brain.process(user_input)

    print(f"\nAIKA > {response}")