// Local bounded graphics fixture: no game files, hooks or external applications.
#include <windows.h>
#include <d3d11.h>
#include <chrono>
LRESULT CALLBACK Procedure(HWND hwnd, UINT msg, WPARAM w, LPARAM l) {
    if (msg == WM_DESTROY) { PostQuitMessage(0); return 0; }
    return DefWindowProcW(hwnd, msg, w, l);
}
int WINAPI wWinMain(HINSTANCE instance, HINSTANCE, PWSTR, int) {
    WNDCLASSW klass{}; klass.lpfnWndProc=Procedure; klass.hInstance=instance; klass.lpszClassName=L"BoosterFpsFixture";
    if (!RegisterClassW(&klass)) return 1;
    HWND window=CreateWindowW(klass.lpszClassName,L"Booster FPS fixture (self-closing)",WS_OVERLAPPEDWINDOW,
                              0,0,640,360,nullptr,nullptr,instance,nullptr);
    if (!window) return 2;
    DXGI_SWAP_CHAIN_DESC description{};
    description.BufferDesc.Width=640;description.BufferDesc.Height=360;description.BufferDesc.Format=DXGI_FORMAT_R8G8B8A8_UNORM;
    description.SampleDesc.Count=1;description.BufferUsage=DXGI_USAGE_RENDER_TARGET_OUTPUT;description.BufferCount=1;
    description.OutputWindow=window;description.Windowed=TRUE;description.SwapEffect=DXGI_SWAP_EFFECT_DISCARD;
    ID3D11Device* device=nullptr;ID3D11DeviceContext* context=nullptr;IDXGISwapChain* swap=nullptr;
    if (FAILED(D3D11CreateDeviceAndSwapChain(nullptr,D3D_DRIVER_TYPE_WARP,nullptr,0,nullptr,0,D3D11_SDK_VERSION,
                                            &description,&swap,&device,nullptr,&context))) return 3;
    ID3D11Texture2D* buffer=nullptr;ID3D11RenderTargetView* target=nullptr;
    if (FAILED(swap->GetBuffer(0,__uuidof(ID3D11Texture2D),reinterpret_cast<void**>(&buffer)))) return 4;
    if (FAILED(device->CreateRenderTargetView(buffer,nullptr,&target))) return 5;
    buffer->Release();ShowWindow(window,SW_SHOW);
    auto end=std::chrono::steady_clock::now()+std::chrono::seconds(15);
    MSG message{};bool done=false;
    while (!done && std::chrono::steady_clock::now()<end) {
        while (PeekMessageW(&message,nullptr,0,0,PM_REMOVE)) {
            if (message.message==WM_QUIT) { done=true; break; }
            TranslateMessage(&message);DispatchMessageW(&message);
        }
        if (done) break;
        float color[]={0.1f,0.1f,0.4f,1.0f};context->ClearRenderTargetView(target,color);
        if (FAILED(swap->Present(1,0))) return 6;
        Sleep(5);
    }
    target->Release();swap->Release();context->Release();device->Release();DestroyWindow(window);return 0;
}
