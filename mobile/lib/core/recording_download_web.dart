import 'package:web/web.dart' as web;

Future<void> saveBrowserRecording(String blobUrl, String fileName) async {
  final anchor = web.HTMLAnchorElement()
    ..href = blobUrl
    ..download = fileName
    ..style.display = 'none';
  web.document.body?.append(anchor);
  anchor.click();
  anchor.remove();
}
