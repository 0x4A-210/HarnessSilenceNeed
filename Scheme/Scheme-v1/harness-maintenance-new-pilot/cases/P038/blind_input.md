# Case ID

P038

## Existing Fuzz Harness H0

### `tools/codecfuzz.cpp`

~~~~cpp
#include "../src/meshoptimizer.h"

#include <stdint.h>
#include <stdlib.h>
#include <string.h>

void fuzzDecoder(const uint8_t* data, size_t size, size_t stride, int (*decode)(void*, size_t, size_t, const unsigned char*, size_t))
{
	size_t count = 66; // must be divisible by 3 for decodeIndexBuffer; should be >=64 to cover large vertex blocks

	void* destination = malloc(count * stride);
	assert(destination);

	int rc = decode(destination, count, stride, reinterpret_cast<const unsigned char*>(data), size);
	(void)rc;

	free(destination);
}

void fuzzRoundtrip(const uint8_t* data, size_t size, size_t stride, int level)
{
	size_t count = size / stride;

	size_t bound = meshopt_encodeVertexBufferBound(count, stride);
	void* encoded = malloc(bound);
	void* decoded = malloc(count * stride);
	assert(encoded && decoded);

	size_t res = meshopt_encodeVertexBufferLevel(static_cast<unsigned char*>(encoded), bound, data, count, stride, level);
	assert(res > 0 && res <= bound);

	// encode again at the boundary to check for memory safety
	// this should produce the same output because encoder is deterministic
	size_t rese = meshopt_encodeVertexBufferLevel(static_cast<unsigned char*>(encoded) + bound - res, res, data, count, stride, level);
	assert(rese == res);

	int rc = meshopt_decodeVertexBuffer(decoded, count, stride, static_cast<unsigned char*>(encoded) + bound - res, res);
	assert(rc == 0);

	assert(memcmp(data, decoded, count * stride) == 0);

	free(decoded);
	free(encoded);
}

extern "C" int LLVMFuzzerTestOneInput(const uint8_t* data, size_t size)
{
	// decodeIndexBuffer supports 2 and 4-byte indices
	fuzzDecoder(data, size, 2, meshopt_decodeIndexBuffer);
	fuzzDecoder(data, size, 4, meshopt_decodeIndexBuffer);

	// decodeIndexSequence supports 2 and 4-byte indices
	fuzzDecoder(data, size, 2, meshopt_decodeIndexSequence);
	fuzzDecoder(data, size, 4, meshopt_decodeIndexSequence);

	// decodeVertexBuffer supports any strides divisible by 4 in 4-256 interval
	// it's a waste of time to check all of them, so we'll just check a few with different alignment mod 16
	fuzzDecoder(data, size, 4, meshopt_decodeVertexBuffer);
	fuzzDecoder(data, size, 16, meshopt_decodeVertexBuffer);
	fuzzDecoder(data, size, 24, meshopt_decodeVertexBuffer);
	fuzzDecoder(data, size, 32, meshopt_decodeVertexBuffer);

	// encodeVertexBuffer/decodeVertexBuffer should roundtrip for any stride, check a few with different alignment mod 16
	// this also checks memory safety properties of the encoder
	// to conserve time, we only check one version/level combination, biased towards version 1
	uint8_t data0 = size > 0 ? data[0] : 0;
	int level = data0 % 5;

	meshopt_encodeVertexVersion(level < 4 ? 1 : 0);

	fuzzRoundtrip(data, size, 4, level);
	fuzzRoundtrip(data, size, 16, level);
	fuzzRoundtrip(data, size, 24, level);
	fuzzRoundtrip(data, size, 32, level);

	return 0;
}
~~~~

## Production Source Change (S0 -> S1)

Harness changes, commit messages, tests, outcomes, and future evidence are excluded. The source diff is complete.

~~~~diff
diff --git a/demo/main.cpp b/demo/main.cpp
index a98c694..a06a54f 100644
--- a/demo/main.cpp
+++ b/demo/main.cpp
@@ -893,7 +893,7 @@ void encodeVertex(const Mesh& mesh, const char* pvn, int level = 2)
 	double start = timestamp();
 
 	std::vector<unsigned char> vbuf(meshopt_encodeVertexBufferBound(mesh.vertices.size(), sizeof(PV)));
-	vbuf.resize(meshopt_encodeVertexBufferLevel(&vbuf[0], vbuf.size(), &pv[0], mesh.vertices.size(), sizeof(PV), level));
+	vbuf.resize(meshopt_encodeVertexBufferLevel(&vbuf[0], vbuf.size(), &pv[0], mesh.vertices.size(), sizeof(PV), level, -1));
 
 	double middle = timestamp();
 
diff --git a/demo/tests.cpp b/demo/tests.cpp
index 1636756..8e9e4a9 100644
--- a/demo/tests.cpp
+++ b/demo/tests.cpp
@@ -616,7 +616,7 @@ static void decodeVertexDeltas()
 	}
 
 	std::vector<unsigned char> buffer(meshopt_encodeVertexBufferBound(16, 8));
-	buffer.resize(meshopt_encodeVertexBufferLevel(&buffer[0], buffer.size(), data, 16, 8, 2));
+	buffer.resize(meshopt_encodeVertexBufferLevel(&buffer[0], buffer.size(), data, 16, 8, 2, -1));
 
 	unsigned short decoded[16 * 4];
 	assert(meshopt_decodeVertexBuffer(decoded, 16, 8, &buffer[0], buffer.size()) == 0);
@@ -637,7 +637,7 @@ static void decodeVertexBitXor()
 	}
 
 	std::vector<unsigned char> buffer(meshopt_encodeVertexBufferBound(16, 16));
-	buffer.resize(meshopt_encodeVertexBufferLevel(&buffer[0], buffer.size(), data, 16, 16, 3));
+	buffer.resize(meshopt_encodeVertexBufferLevel(&buffer[0], buffer.size(), data, 16, 16, 3, -1));
 
 	unsigned int decoded[16 * 4];
 	assert(meshopt_decodeVertexBuffer(decoded, 16, 16, &buffer[0], buffer.size()) == 0);
diff --git a/src/meshoptimizer.h b/src/meshoptimizer.h
index 84ba1a7..ef6c4a9 100644
--- a/src/meshoptimizer.h
+++ b/src/meshoptimizer.h
@@ -304,8 +304,9 @@ MESHOPTIMIZER_API size_t meshopt_encodeVertexBufferBound(size_t vertex_count, si
  * The default compression level implied by meshopt_encodeVertexBuffer is 2.
  *
  * level should be in the range [0, 3] with 0 being the fastest and 3 being the slowest and producing the best compression ratio.
+ * version should be -1 to use the default version (specified via meshopt_encodeVertexVersion), or 0/1 to override the version; per above, level won't take effect if version is 0.
  */
-MESHOPTIMIZER_EXPERIMENTAL size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer, size_t buffer_size, const void* vertices, size_t vertex_count, size_t vertex_size, int level);
+MESHOPTIMIZER_EXPERIMENTAL size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer, size_t buffer_size, const void* vertices, size_t vertex_count, size_t vertex_size, int level, int version);
 
 /**
  * Set vertex encoder format version
diff --git a/src/vertexcodec.cpp b/src/vertexcodec.cpp
index 53cf9d7..847589b 100644
--- a/src/vertexcodec.cpp
+++ b/src/vertexcodec.cpp
@@ -1643,13 +1643,16 @@ static unsigned int cpuid = getCpuFeatures();
 
 } // namespace meshopt
 
-size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer, size_t buffer_size, const void* vertices, size_t vertex_count, size_t vertex_size, int level)
+size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer, size_t buffer_size, const void* vertices, size_t vertex_count, size_t vertex_size, int level, int version)
 {
 	using namespace meshopt;
 
 	assert(vertex_size > 0 && vertex_size <= 256);
 	assert(vertex_size % 4 == 0);
 	assert(level >= 0 && level <= 9); // only a subset of this range is used right now
+	assert(version < 0 || unsigned(version) <= kDecodeVertexVersion);
+
+	version = version < 0 ? gEncodeVertexVersion : version;
 
 #if TRACE
 	memset(vertexstats, 0, sizeof(vertexstats));
@@ -1663,8 +1666,6 @@ size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer, size_t buffer_size
 	if (size_t(data_end - data) < 1)
 		return 0;
 
-	int version = gEncodeVertexVersion;
-
 	*data++ = (unsigned char)(kVertexHeader | version);
 
 	unsigned char first_vertex[256] = {};
@@ -1777,7 +1778,7 @@ size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer, size_t buffer_size
 
 size_t meshopt_encodeVertexBuffer(unsigned char* buffer, size_t buffer_size, const void* vertices, size_t vertex_count, size_t vertex_size)
 {
-	return meshopt_encodeVertexBufferLevel(buffer, buffer_size, vertices, vertex_count, vertex_size, meshopt::kEncodeDefaultLevel);
+	return meshopt_encodeVertexBufferLevel(buffer, buffer_size, vertices, vertex_count, vertex_size, meshopt::kEncodeDefaultLevel, meshopt::gEncodeVertexVersion);
 }
 
 size_t meshopt_encodeVertexBufferBound(size_t vertex_count, size_t vertex_size)
diff --git a/tools/codectest.cpp b/tools/codectest.cpp
index 28203ec..04ba873 100644
--- a/tools/codectest.cpp
+++ b/tools/codectest.cpp
@@ -91,7 +91,7 @@ void testFile(FILE* file, size_t count, size_t stride, int level, Stats* stats =
 
 	std::vector<unsigned char> output(meshopt_encodeVertexBufferBound(count, stride));
 	meshopt_encodeVertexVersion(1);
-	output.resize(meshopt_encodeVertexBufferLevel(output.data(), output.size(), decoded.data(), count, stride, level));
+	output.resize(meshopt_encodeVertexBufferLevel(output.data(), output.size(), decoded.data(), count, stride, level, -1));
 
 	printf(" raw %zu KB\t", decoded.size() / 1024);
 	printf(" v0 %.3f", double(input.size()) / double(decoded.size()));
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
