# Writing the reports

The Writer and its checker follow these rules for every report of this project. They are yours: change them as you like.

## Who reads the report

- The reader is a scientist in the field who did not follow the work: they do not know the names the agents gave things, the files they made or the checks they ran. Write so that they can follow the report without opening anything else.

## Structure: the answer first

- Open with the main results themselves, on the first page and in plain words: the equations, the values with their units and uncertainty, the key figure, the decision. When a result is an expression (a Hamiltonian, a formula, a model), write it as a displayed equation with every symbol defined and the physical meaning of each term; a table of numbers may accompany it, never replace it. "Met" or "checked" is a verdict on a result, not the result.
- Then give one section per main result: the argument that leads to it (what it rests on and how it follows), what it means, and where it stops holding.
- Then the limitations and open issues; the negative results and failed approaches, briefly, with what they rule out; and the key decisions that shape the results (the model, the approximations, the tolerances), each with its reason in a sentence.
- Close with the evidence, in appendices: how each key result was checked (convergence, limiting cases, comparisons), and a reproduction appendix saying where the code, the data and the commands of each result are in the project.

## The argument

- Every statement follows from the ones before it. Connect the paragraphs: each says why it comes next and how it builds on the previous one, so that the text reads as one argument, not as a list of steps.
- Report what the reader needs, not everything that was done: detailed scans, intermediate steps and checks that change no conclusion stay in the agents' work, referred to from the evidence. If a reader would ask why something is there, take it out or move it to the evidence.
- In the text, give only the numbers the argument needs, with the digits it needs.

## Language and mathematics

- Use the words of the field and of the human's documents, plainly; avoid needlessly formal or complicated language, but stay precise. Define every term where it first appears.
- Keep the quantities a derivation starts from visible until its end: write substitutions out instead of hiding them behind new symbols, and never build chains of definitions, each through the previous one.
- Introduce a symbol only for a quantity of physical interest; define it once, in terms of the original quantities, and say what it means.
- A name the agents coined (for a device, a run, a tolerance, a method) never stands in for its plain description.

## Figures

- Every figure is referred to in the text where it is needed, and its caption says what is plotted, what is held fixed, and how to read it.
