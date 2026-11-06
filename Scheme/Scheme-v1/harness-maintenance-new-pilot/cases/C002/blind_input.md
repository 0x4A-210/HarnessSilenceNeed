# Case ID

C002

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

	meshopt_encodeVertexVersion(level < 4 ? 0xe : 0);

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
index 27dc8eb..6b11857 100644
--- a/demo/main.cpp
+++ b/demo/main.cpp
@@ -1407,7 +1407,7 @@ void processDev(const char* path)
 
 	meshopt_encodeVertexVersion(0);
 	encodeVertex<PackedVertex>(copy, "L");
-	meshopt_encodeVertexVersion(0xe);
+	meshopt_encodeVertexVersion(1);
 	encodeVertex<PackedVertex>(copy, "0", 0);
 	encodeVertex<PackedVertex>(copy, "1", 1);
 	encodeVertex<PackedVertex>(copy, "2", 2);
@@ -1427,7 +1427,7 @@ int main(int argc, char** argv)
 {
 	void runTests();
 
-	meshopt_encodeVertexVersion(0);
+	meshopt_encodeVertexVersion(1);
 	meshopt_encodeIndexVersion(1);
 
 	if (argc == 1)
diff --git a/demo/tests.cpp b/demo/tests.cpp
index 260878a..5d15aa1 100644
--- a/demo/tests.cpp
+++ b/demo/tests.cpp
@@ -59,7 +59,7 @@ static const unsigned char kVertexDataV0[] = {
 };
 
 static const unsigned char kVertexDataV1[] = {
-    0xae, 0xee, 0xaa, 0xee, 0x00, 0x4b, 0x4b, 0x4b, 0x00, 0x00, 0x4b, 0x00, 0x00, 0x7d, 0x7d, 0x7d,
+    0xa1, 0xee, 0xaa, 0xee, 0x00, 0x4b, 0x4b, 0x4b, 0x00, 0x00, 0x4b, 0x00, 0x00, 0x7d, 0x7d, 0x7d,
     0x00, 0x00, 0x7d, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x62, 0x00, 0x62, // clang-format :-/
 };
@@ -68,7 +68,7 @@ static const unsigned char kVertexDataV1[] = {
 // the encoder that exercised all features of the format; because of this it is much larger
 // and will never be produced by the encoder itself.
 static const unsigned char kVertexDataV1Custom[] = {
-    0xae, 0xd4, 0x94, 0xd4, 0x01, 0x0e, 0x00, 0x58, 0x57, 0x58, 0x02, 0x02, 0x12, 0x00, 0x00, 0x00,
+    0xa1, 0xd4, 0x94, 0xd4, 0x01, 0x0e, 0x00, 0x58, 0x57, 0x58, 0x02, 0x02, 0x12, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x58, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00,
     0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x03, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00,
@@ -2060,18 +2060,16 @@ void runTests()
 	encodeIndexSequenceEmpty();
 
 	decodeVertexV0();
-	encodeVertexMemorySafe();
-	decodeVertexMemorySafe();
-	decodeVertexRejectExtraBytes();
-	decodeVertexRejectMalformedHeaders();
-
 	decodeVertexV1();
 	decodeVertexV1Custom();
 
 	for (int version = 0; version <= 1; ++version)
 	{
-		meshopt_encodeVertexVersion(version == 1 ? 0xe : version);
+		meshopt_encodeVertexVersion(version);
 
+		decodeVertexMemorySafe();
+		decodeVertexRejectExtraBytes();
+		decodeVertexRejectMalformedHeaders();
 		decodeVertexBitGroups();
 		decodeVertexBitGroupSentinels();
 		decodeVertexDeltas();
@@ -2079,10 +2077,9 @@ void runTests()
 		decodeVertexLarge();
 		decodeVertexSmall();
 		encodeVertexEmpty();
+		encodeVertexMemorySafe();
 	}
 
-	meshopt_encodeVertexVersion(0);
-
 	decodeFilterOct8();
 	decodeFilterOct12();
 	decodeFilterQuat12();
diff --git a/gltf/gltfpack.cpp b/gltf/gltfpack.cpp
index 88ae1e6..c22d252 100644
--- a/gltf/gltfpack.cpp
+++ b/gltf/gltfpack.cpp
@@ -1514,15 +1514,13 @@ int main(int argc, char** argv)
 			settings.compress = true;
 			settings.fallback = true;
 		}
-#ifndef NDEBUG
 		else if (strcmp(arg, "-ce") == 0)
 		{
-			fprintf(stderr, "Warning: experimental compression will produce files that may not decode in the future!\n");
-			meshopt_encodeVertexVersion(0xe);
+			fprintf(stderr, "Warning: experimental compression will produce files that are not compliant with EXT_meshopt_compression\n");
+			meshopt_encodeVertexVersion(1);
 			settings.compress = true;
 			settings.compressmore = true;
 		}
-#endif
 		else if (strcmp(arg, "-v") == 0)
 		{
 			settings.verbose = 1;
diff --git a/src/meshoptimizer.h b/src/meshoptimizer.h
index 6243947..e066041 100644
--- a/src/meshoptimizer.h
+++ b/src/meshoptimizer.h
@@ -289,7 +289,7 @@ MESHOPTIMIZER_API size_t meshopt_encodeVertexBufferLevel(unsigned char* buffer,
 
 /**
  * Set vertex encoder format version
- * version must specify the data format version to encode; valid values are 0 (decodable by all library versions)
+ * version must specify the data format version to encode; valid values are 0 (decodable by all library versions) and 1 (decodable by 0.23+)
  */
 MESHOPTIMIZER_API void meshopt_encodeVertexVersion(int version);
 
diff --git a/src/vertexcodec.cpp b/src/vertexcodec.cpp
index d3fc7bb..43019cb 100644
--- a/src/vertexcodec.cpp
+++ b/src/vertexcodec.cpp
@@ -1768,8 +1768,7 @@ size_t meshopt_encodeVertexBufferBound(size_t vertex_count, size_t vertex_size)
 
 void meshopt_encodeVertexVersion(int version)
 {
-	// note: this version is experimental and the binary format is not finalized; this should not be used in production!
-	assert(unsigned(version) <= 0 || version == 0xe);
+	assert(unsigned(version) <= 1);
 
 	meshopt::gEncodeVertexVersion = version;
 }
@@ -1810,7 +1809,7 @@ int meshopt_decodeVertexBuffer(void* destination, size_t vertex_count, size_t ve
 		return -1;
 
 	int version = data_header & 0x0f;
-	if (version > 0 && version != 0xe)
+	if (version > 1)
 		return -1;
 
 	size_t tail_size = vertex_size + (version == 0 ? 0 : vertex_size / 4);
diff --git a/tools/codecbench.cpp b/tools/codecbench.cpp
index 0b67c58..cc1eac0 100644
--- a/tools/codecbench.cpp
+++ b/tools/codecbench.cpp
@@ -207,7 +207,7 @@ File readFile(const char* path)
 	result.v0.resize(meshopt_encodeVertexBufferBound(result.count, result.stride));
 	result.v0.resize(meshopt_encodeVertexBuffer(result.v0.data(), result.v0.size(), decoded.data(), result.count, result.stride));
 
-	meshopt_encodeVertexVersion(0xe);
+	meshopt_encodeVertexVersion(1);
 	result.v1.resize(meshopt_encodeVertexBufferBound(result.count, result.stride));
 	result.v1.resize(meshopt_encodeVertexBuffer(result.v1.data(), result.v1.size(), decoded.data(), result.count, result.stride));
 
@@ -252,7 +252,7 @@ int main(int argc, char** argv)
 
 		std::vector<unsigned char> buffer(max_size);
 
-		printf("Algorithm   :\tvtx\tvtxe\n");
+		printf("Algorithm   :\tvtx0\tvtx1\n");
 		printf("Size (MB)   :\t%.2f\t%.2f\n", double(total_v0) / 1024 / 1024, double(total_v1) / 1024 / 1024);
 		printf("Ratio       :\t%.2f\t%.2f\n", double(total_v0) / double(total_size), double(total_v1) / double(total_size));
 
@@ -334,7 +334,7 @@ int main(int argc, char** argv)
 		}
 	}
 
-	printf("Algorithm   :\tvtx\tvtxe\tidx\toct8\toct12\tquat12\texp\n");
+	printf("Algorithm   :\tvtx0\tvtx1\tidx\toct8\toct12\tquat12\texp\n");
 
 	for (int l = 0; l < (loop ? 100 : 1); ++l)
 	{
@@ -343,7 +343,7 @@ int main(int argc, char** argv)
 		double bestvd0 = 0, bestid = 0;
 		benchCodecs(vertices, indices, bestvd0, bestid, verbose);
 
-		meshopt_encodeVertexVersion(0xe);
+		meshopt_encodeVertexVersion(1);
 
 		double bestvd1 = 0, bestidr = 0;
 		benchCodecs(vertices, indices, bestvd1, bestidr, verbose);
diff --git a/tools/codectest.cpp b/tools/codectest.cpp
index 48d2f9e..529a27c 100644
--- a/tools/codectest.cpp
+++ b/tools/codectest.cpp
@@ -68,9 +68,10 @@ void testFile(FILE* file, size_t count, size_t stride, int level, Stats* stats =
 	int res = meshopt_decodeVertexBuffer(&decoded[0], count, stride, &input[0], input.size());
 	if (res != 0 && input.size() == decoded.size())
 	{
-		// some files are not encoded; encode them with v1 to let the rest of the flow proceed as is
+		// some files are not encoded; encode them with v0 to let the rest of the flow proceed as is
 		memcpy(decoded.data(), input.data(), decoded.size());
 		input.resize(meshopt_encodeVertexBufferBound(count, stride));
+		meshopt_encodeVertexVersion(0);
 		input.resize(meshopt_encodeVertexBuffer(input.data(), input.size(), decoded.data(), count, stride));
 	}
 	else if (res != 0)
@@ -80,9 +81,8 @@ void testFile(FILE* file, size_t count, size_t stride, int level, Stats* stats =
 	}
 
 	std::vector<unsigned char> output(meshopt_encodeVertexBufferBound(count, stride));
-	meshopt_encodeVertexVersion(0xe);
+	meshopt_encodeVertexVersion(1);
 	output.resize(meshopt_encodeVertexBufferLevel(output.data(), output.size(), decoded.data(), count, stride, level));
-	meshopt_encodeVertexVersion(0);
 
 	printf(" raw %zu KB\t", decoded.size() / 1024);
 	printf(" v0 %.2f", double(input.size()) / double(decoded.size()));
@@ -205,6 +205,7 @@ int main(int argc, char** argv)
 	}
 	else
 	{
+		meshopt_encodeVertexVersion(1);
 		size_t vertex_count = input.size() / stride;
 		std::vector<unsigned char> output(meshopt_encodeVertexBufferBound(vertex_count, stride));
 		size_t output_size = meshopt_encodeVertexBuffer(output.data(), output.size(), input.data(), vertex_count, stride);
~~~~

## Available Context

Only H0 and the S0-to-S1 production diff above are evidence. Analyze this case according to the fixed baseline prompt.
