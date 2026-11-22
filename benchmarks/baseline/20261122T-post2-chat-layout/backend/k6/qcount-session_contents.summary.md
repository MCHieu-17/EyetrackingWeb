# k6 summary

scenario: session_contents

- http_req_duration: p(95)=15.225, p(99)=15.301, avg=9.820, min=2.884, med=9.849, max=15.320, p(90)=13.314
- http_req_blocked: p(95)=0.042, p(99)=0.271, avg=0.027, min=0.003, med=0.011, max=0.328, p(90)=0.022
- http_req_connecting: p(90)=0.000, p(95)=0.014, p(99)=0.222, avg=0.014, min=0.000, med=0.000, max=0.274
- iterations: count=20.000, rate=4.741
- http_req_duration{expected_response:true}: p(95)=15.225, p(99)=15.301, avg=9.820, min=2.884, med=9.849, max=15.320, p(90)=13.314
- http_req_receiving: avg=0.095, min=0.031, med=0.098, max=0.192, p(90)=0.168, p(95)=0.189, p(99)=0.191
- http_req_tls_handshaking: p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000
- vus: max=1.000, min=1.000
- http_req_waiting: p(95)=15.061, p(99)=15.160, avg=9.683, min=2.832, med=9.687, max=15.185, p(90)=13.154
- http_req_failed: rate=0.000
- http_req_sending: max=0.069, p(90)=0.054, p(95)=0.061, p(99)=0.068, avg=0.043, min=0.013, med=0.043
