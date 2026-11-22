# k6 summary

scenario: session_contents

- http_req_blocked: min=0.002, med=0.011, max=0.217, p(90)=0.013, p(95)=0.014, p(99)=0.197, avg=0.014
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_waiting: min=2.706, med=11.176, max=67.860, p(90)=18.363, p(95)=18.993, p(99)=22.465, avg=11.790
- http_req_receiving: p(99)=0.393, avg=0.109, min=0.007, med=0.093, max=0.439, p(90)=0.215, p(95)=0.264
- http_req_duration: p(99)=22.637, avg=11.937, min=2.750, med=11.353, max=67.946, p(90)=18.465, p(95)=19.122
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- http_req_sending: min=0.007, med=0.040, max=0.128, p(90)=0.051, p(95)=0.057, p(99)=0.085, avg=0.038
- http_req_connecting: p(95)=0.000, p(99)=0.145, avg=0.003, min=0.000, med=0.000, max=0.163, p(90)=0.000
- http_req_duration{expected_response:true}: med=11.353, max=67.946, p(90)=18.465, p(95)=19.122, p(99)=22.637, avg=11.937, min=2.750
- iterations: count=238.000, rate=23.448
