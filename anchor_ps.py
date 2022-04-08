import click
from tabulate import tabulate

@click.command()
def ps():
    values = []
    with open("containers.txt","r") as f:
    	for line in f:
    		currentline = line.split(",")
    		values.append(currentline)

    print(tabulate(values, headers=["PID", "Container ID", "Image", "Command", "Created"]))


if __name__ == '__main__':
    ps()
