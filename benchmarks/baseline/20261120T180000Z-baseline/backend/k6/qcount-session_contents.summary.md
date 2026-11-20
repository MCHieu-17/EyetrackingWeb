# k6 summary

scenario: session_contents

- vus: min=1.000, max=1.000
- http_req_duration: p(95)=23.384, p(99)=25.188, avg=18.450, min=4.927, med=21.032, max=25.639, p(90)=22.569
- http_req_blocked: p(99)=0.110, avg=0.018, min=0.003, med=0.011, max=0.129, p(90)=0.023, p(95)=0.032
- http_req_receiving: avg=0.128, min=0.037, med=0.111, max=0.276, p(90)=0.211, p(95)=0.226, p(99)=0.266
- iterations: count=20.000, rate=4.554
- http_req_failed: rate=0.000
- http_req_sending: p(95)=0.054, p(99)=0.057, avg=0.041, min=0.013, med=0.042, max=0.058, p(90)=0.054
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: max=25.319, p(90)=22.328, p(95)=23.224, p(99)=24.900, avg=18.281, min=4.876, med=20.876
- http_req_duration{expected_response:true}: p(99)=25.188, avg=18.450, min=4.927, med=21.032, max=25.639, p(90)=22.569, p(95)=23.384
- http_req_connecting: max=0.094, p(90)=0.000, p(95)=0.005, p(99)=0.076, avg=0.005, min=0.000, med=0.000
