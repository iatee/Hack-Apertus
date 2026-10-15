.PHONY: run

# The project root is track_2a/; this just forwards in case `make run` is called from here.
run:
	$(MAKE) -C track_2a run
