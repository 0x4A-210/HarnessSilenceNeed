# Case ID

P039

## Existing Fuzz Harness H0

### `tools/clusterfuzz.cpp`

~~~~cpp
#include "../src/meshoptimizer.h"

#include <float.h>
#include <stdint.h>
#include <stdlib.h>

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* buffer, size_t size)
{
	if (size == 0)
		return 0;

	srand(buffer[0]);

	float vb[100][4];

	for (int i = 0; i < 100; ++i)
	{
		vb[i][0] = rand() % 10;
		vb[i][1] = rand() % 10;
		vb[i][2] = rand() % 10;
		vb[i][3] = rand() % 10;
	}

	unsigned int ib[999];
	int indices = (size - 1) < 999 ? (size - 1) / 3 * 3 : 999;

	for (int i = 0; i < indices; ++i)
		ib[i] = buffer[1 + i] % 100;

	meshopt_Meshlet ml[333];
	unsigned int mv[333 * 3];
	unsigned char mt[333 * 4];

	meshopt_buildMeshlets(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 4, /* max_triangles= */ 4, 0.f);

	meshopt_buildMeshletsScan(ml, mv, mt, ib, indices, 100, /* max_vertices= */ 4, /* max_triangles= */ 4);
	meshopt_buildMeshletsScan(ml, mv, mt, ib, indices, 100, /* max_vertices= */ 4, /* max_triangles= */ 8);

	meshopt_buildMeshletsFlex(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 4, /* min_triangles= */ 4, /* max_triangles= */ 8, 0.f, 2.f);
	meshopt_buildMeshletsFlex(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 8, /* min_triangles= */ 8, /* max_triangles= */ 16, 0.f, 2.f);
	meshopt_buildMeshletsFlex(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 16, /* min_triangles= */ 8, /* max_triangles= */ 32, 0.f, 2.f);
	meshopt_buildMeshletsFlex(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 16, /* min_triangles= */ 16, /* max_triangles= */ 32, 0.f, 2.f);

	meshopt_buildMeshletsSplit(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 4, /* min_triangles= */ 4, /* max_triangles= */ 8, 0.f);
	meshopt_buildMeshletsSplit(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 8, /* min_triangles= */ 4, /* max_triangles= */ 32, 0.f);
	meshopt_buildMeshletsSplit(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 8, /* min_triangles= */ 8, /* max_triangles= */ 32, 0.f);
	meshopt_buildMeshletsSplit(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 8, /* min_triangles= */ 12, /* max_triangles= */ 32, 0.f);
	meshopt_buildMeshletsSplit(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 16, /* min_triangles= */ 16, /* max_triangles= */ 32, 0.f);
	meshopt_buildMeshletsSplit(ml, mv, mt, ib, indices, vb[0], 100, sizeof(float) * 4, /* max_vertices= */ 16, /* min_triangles= */ 32, /* max_triangles= */ 32, 0.f);

	return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/demo/main.cpp b/demo/main.cpp
index 9e925cf..187a25e 100644
--- a/demo/main.cpp
+++ b/demo/main.cpp
@@ -995,13 +995,13 @@ static int follow(int* parents, int index)
 	return index;
 }
 
-void meshlets(const Mesh& mesh, bool scan = false, bool uniform = false, bool flex = false, bool split = false, bool dump = false)
+void meshlets(const Mesh& mesh, bool scan = false, bool uniform = false, bool flex = false, bool spatial = false, bool dump = false)
 {
 	// NVidia-recommends 64/126; we round 126 down to a multiple of 4
 	// alternatively we also test uniform configuration with 64/64 which is better for AMD
 	const size_t max_vertices = 64;
 	const size_t max_triangles = uniform ? 64 : 124;
-	const size_t min_triangles = split ? 16 : (uniform ? 24 : 32); // only used in flex/split modes
+	const size_t min_triangles = spatial ? 16 : (uniform ? 24 : 32); // only used in flex/spatial modes
 
 	// note: should be set to 0 unless cone culling is used at runtime!
 	const float cone_weight = flex ? -1.0f : 0.25f;
@@ -1018,8 +1018,8 @@ void meshlets(const Mesh& mesh, bool scan = false, bool uniform = false, bool fl
 		meshlets.resize(meshopt_buildMeshletsScan(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &mesh.indices[0], mesh.indices.size(), mesh.vertices.size(), max_vertices, max_triangles));
 	else if (flex)
 		meshlets.resize(meshopt_buildMeshletsFlex(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &mesh.indices[0], mesh.indices.size(), &mesh.vertices[0].px, mesh.vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, cone_weight, split_factor));
-	else if (split)
-		meshlets.resize(meshopt_buildMeshletsSplit(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &mesh.indices[0], mesh.indices.size(), &mesh.vertices[0].px, mesh.vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, 0.f));
+	else if (spatial)
+		meshlets.resize(meshopt_buildMeshletsSpatial(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &mesh.indices[0], mesh.indices.size(), &mesh.vertices[0].px, mesh.vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, 0.f));
 	else // note: equivalent to the call of buildMeshletsFlex() with non-negative cone_weight and split_factor = 0
 		meshlets.resize(meshopt_buildMeshlets(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &mesh.indices[0], mesh.indices.size(), &mesh.vertices[0].px, mesh.vertices.size(), sizeof(Vertex), max_vertices, max_triangles, cone_weight));
 
@@ -1112,7 +1112,7 @@ void meshlets(const Mesh& mesh, bool scan = false, bool uniform = false, bool fl
 	avg_connected /= double(meshlets.size());
 
 	printf("Meshlets%c: %d meshlets (avg vertices %.1f, avg triangles %.1f, avg boundary %.1f, avg connected %.2f, not full %d) in %.2f msec\n",
-	    scan ? 'S' : (flex ? 'F' : (split ? 'X' : (uniform ? 'U' : ' '))),
+	    scan ? 'S' : (flex ? 'F' : (spatial ? 'X' : (uniform ? 'U' : ' '))),
 	    int(meshlets.size()), avg_vertices, avg_triangles, avg_boundary, avg_connected, int(not_full), (end - start) * 1000);
 
 	float camera[3] = {100, 100, 100};
@@ -1526,7 +1526,7 @@ void process(const char* path)
 	meshlets(copy, /* scan= */ false);
 	meshlets(copy, /* scan= */ false, /* uniform= */ true);
 	meshlets(copy, /* scan= */ false, /* uniform= */ false, /* flex= */ true);
-	meshlets(copy, /* scan= */ false, /* uniform= */ true, /* flex= */ false, /* split= */ true);
+	meshlets(copy, /* scan= */ false, /* uniform= */ true, /* flex= */ false, /* spatial= */ true);
 
 	shadow(copy);
 	tessellationAdjacency(copy);
diff --git a/demo/nanite.cpp b/demo/nanite.cpp
index d1a5da6..bf36330 100644
--- a/demo/nanite.cpp
+++ b/demo/nanite.cpp
@@ -68,7 +68,7 @@ const size_t kGroupSize = 8;
 const bool kUseLocks = true;
 const bool kUseNormals = true;
 const bool kUseRetry = true;
-const bool kUseSplit = false;
+const bool kUseSpatial = false;
 const int kMetisSlop = 2;
 const float kSimplifyThreshold = 0.85f;
 
@@ -138,8 +138,8 @@ static std::vector<Cluster> clusterize(const std::vector<Vertex>& vertices, cons
 	std::vector<unsigned int> meshlet_vertices(max_meshlets * max_vertices);
 	std::vector<unsigned char> meshlet_triangles(max_meshlets * max_triangles * 3);
 
-	if (kUseSplit)
-		meshlets.resize(meshopt_buildMeshletsSplit(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &indices[0], indices.size(), &vertices[0].px, vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, fill_weight));
+	if (kUseSpatial)
+		meshlets.resize(meshopt_buildMeshletsSpatial(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &indices[0], indices.size(), &vertices[0].px, vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, fill_weight));
 	else
 		meshlets.resize(meshopt_buildMeshletsFlex(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &indices[0], indices.size(), &vertices[0].px, vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, 0.f, split_factor));
 
@@ -926,7 +926,7 @@ void clrt(const std::vector<Vertex>& vertices, const std::vector<unsigned int>&
 
 	double middle = timestamp();
 
-	const bool use_splitalgo = true;
+	const bool use_spatial = true;
 	const size_t max_vertices = 64;
 	const size_t min_triangles = 16;
 	const size_t max_triangles = 64;
@@ -940,8 +940,8 @@ void clrt(const std::vector<Vertex>& vertices, const std::vector<unsigned int>&
 	std::vector<unsigned int> meshlet_vertices(max_meshlets * max_vertices);
 	std::vector<unsigned char> meshlet_triangles(max_meshlets * max_triangles * 3);
 
-	if (use_splitalgo)
-		meshlets.resize(meshopt_buildMeshletsSplit(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &indices[0], indices.size(), &vertices[0].px, vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, fill_weight));
+	if (use_spatial)
+		meshlets.resize(meshopt_buildMeshletsSpatial(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &indices[0], indices.size(), &vertices[0].px, vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, fill_weight));
 	else
 		meshlets.resize(meshopt_buildMeshletsFlex(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &indices[0], indices.size(), &vertices[0].px, vertices.size(), sizeof(Vertex), max_vertices, min_triangles, max_triangles, cone_weight, split_factor));
 
diff --git a/demo/tests.cpp b/demo/tests.cpp
index 848da67..0ae938e 100644
--- a/demo/tests.cpp
+++ b/demo/tests.cpp
@@ -1321,7 +1321,7 @@ static void meshletsMax()
 	}
 }
 
-static void meshletsSplit()
+static void meshletsSpatial()
 {
 	// two tetrahedrons far apart
 	float vb[2 * 4 * 3] = {
@@ -1342,25 +1342,25 @@ static void meshletsSplit()
 	unsigned char mt[2 * 8 * 3]; // 2 meshlets with up to 8 triangles
 
 	// with strict limits, we should get one meshlet (maxt=8) or two (maxt=4)
-	assert(meshopt_buildMeshletsSplit(ml, mv, mt, ib, sizeof(ib) / sizeof(ib[0]), vb, 8, sizeof(float) * 3, 16, 8, 8, 0.f) == 1);
+	assert(meshopt_buildMeshletsSpatial(ml, mv, mt, ib, sizeof(ib) / sizeof(ib[0]), vb, 8, sizeof(float) * 3, 16, 8, 8, 0.f) == 1);
 	assert(ml[0].triangle_count == 8);
 	assert(ml[0].vertex_count == 8);
 
-	assert(meshopt_buildMeshletsSplit(ml, mv, mt, ib, sizeof(ib) / sizeof(ib[0]), vb, 8, sizeof(float) * 3, 16, 4, 4, 0.f) == 2);
+	assert(meshopt_buildMeshletsSpatial(ml, mv, mt, ib, sizeof(ib) / sizeof(ib[0]), vb, 8, sizeof(float) * 3, 16, 4, 4, 0.f) == 2);
 	assert(ml[0].triangle_count == 4);
 	assert(ml[0].vertex_count == 4);
 	assert(ml[1].triangle_count == 4);
 	assert(ml[1].vertex_count == 4);
 
 	// with maxv=4 we should get two meshlets since we can't accomodate both
-	assert(meshopt_buildMeshletsSplit(ml, mv, mt, ib, sizeof(ib) / sizeof(ib[0]), vb, 8, sizeof(float) * 3, 4, 4, 8, 0.f) == 2);
+	assert(meshopt_buildMeshletsSpatial(ml, mv, mt, ib, sizeof(ib) / sizeof(ib[0]), vb, 8, sizeof(float) * 3, 4, 4, 8, 0.f) == 2);
 	assert(ml[0].triangle_count == 4);
 	assert(ml[0].vertex_count == 4);
 	assert(ml[1].triangle_count == 4);
 	assert(ml[1].vertex_count == 4);
 }
 
-static void meshletsSplitDeep()
+static void meshletsSpatialDeep()
 {
 	const int N = 400;
 	const size_t max_vertices = 4;
@@ -1384,7 +1384,7 @@ static void meshletsSplitDeep()
 	std::vector<unsigned int> meshlet_vertices(max_meshlets * max_vertices);
 	std::vector<unsigned char> meshlet_triangles(max_meshlets * max_triangles * 3);
 
-	size_t result = meshopt_buildMeshletsSplit(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &ib[0], N * 3, &vb[0], N + 1, sizeof(float) * 3, max_vertices, max_triangles, max_triangles, 0.f);
+	size_t result = meshopt_buildMeshletsSpatial(&meshlets[0], &meshlet_vertices[0], &meshlet_triangles[0], &ib[0], N * 3, &vb[0], N + 1, sizeof(float) * 3, max_vertices, max_triangles, max_triangles, 0.f);
 	assert(result == N);
 }
 
@@ -2581,8 +2581,8 @@ void runTests()
 	meshletsSparse();
 	meshletsFlex();
 	meshletsMax();
-	meshletsSplit();
-	meshletsSplitDeep();
+	meshletsSpatial();
+	meshletsSpatialDeep();
 
 	partitionBasic();
 	partitionSpatial();
diff --git a/src/clusterizer.cpp b/src/clusterizer.cpp
index 19a335b..be7478d 100644
--- a/src/clusterizer.cpp
+++ b/src/clusterizer.cpp
@@ -1300,7 +1300,7 @@ size_t meshopt_buildMeshletsScan(meshopt_Meshlet* meshlets, unsigned int* meshle
 	return meshlet_offset;
 }
 
-size_t meshopt_buildMeshletsSplit(struct meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const unsigned int* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight)
+size_t meshopt_buildMeshletsSpatial(struct meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const unsigned int* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight)
 {
 	using namespace meshopt;
 
diff --git a/src/meshoptimizer.h b/src/meshoptimizer.h
index b963719..eacd14d 100644
--- a/src/meshoptimizer.h
+++ b/src/meshoptimizer.h
@@ -619,7 +619,7 @@ MESHOPTIMIZER_EXPERIMENTAL size_t meshopt_buildMeshletsFlex(struct meshopt_Meshl
  * max_vertices, min_triangles and max_triangles must not exceed implementation limits (max_vertices <= 256, max_triangles <= 512; min_triangles <= max_triangles; both min_triangles and max_triangles must be divisible by 4)
  * fill_weight allows to prioritize clusters that are closer to maximum size at some cost to SAH quality; 0.5 is a safe default
  */
-MESHOPTIMIZER_EXPERIMENTAL size_t meshopt_buildMeshletsSplit(struct meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const unsigned int* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight);
+MESHOPTIMIZER_EXPERIMENTAL size_t meshopt_buildMeshletsSpatial(struct meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const unsigned int* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight);
 
 /**
  * Meshlet optimizer
@@ -851,7 +851,7 @@ inline size_t meshopt_buildMeshletsScan(meshopt_Meshlet* meshlets, unsigned int*
 template <typename T>
 inline size_t meshopt_buildMeshletsFlex(meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const T* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float cone_weight, float split_factor);
 template <typename T>
-inline size_t meshopt_buildMeshletsSplit(meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const T* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight);
+inline size_t meshopt_buildMeshletsSpatial(meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const T* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight);
 template <typename T>
 inline meshopt_Bounds meshopt_computeClusterBounds(const T* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride);
 template <typename T>
@@ -1290,11 +1290,11 @@ inline size_t meshopt_buildMeshletsFlex(meshopt_Meshlet* meshlets, unsigned int*
 }
 
 template <typename T>
-inline size_t meshopt_buildMeshletsSplit(meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const T* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight)
+inline size_t meshopt_buildMeshletsSpatial(meshopt_Meshlet* meshlets, unsigned int* meshlet_vertices, unsigned char* meshlet_triangles, const T* indices, size_t index_count, const float* vertex_positions, size_t vertex_count, size_t vertex_positions_stride, size_t max_vertices, size_t min_triangles, size_t max_triangles, float fill_weight)
 {
 	meshopt_IndexAdapter<T> in(NULL, indices, index_count);
 
-	return meshopt_buildMeshletsSplit(meshlets, meshlet_vertices, meshlet_triangles, in.data, index_count, vertex_positions, vertex_count, vertex_positions_stride, max_vertices, min_triangles, max_triangles, fill_weight);
+	return meshopt_buildMeshletsSpatial(meshlets, meshlet_vertices, meshlet_triangles, in.data, index_count, vertex_positions, vertex_count, vertex_positions_stride, max_vertices, min_triangles, max_triangles, fill_weight);
 }
 
 template <typename T>
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
