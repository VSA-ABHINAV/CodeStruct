from analyzer import analyze_project

result = analyze_project("../sample_project")


for file in result:
    print(file)
