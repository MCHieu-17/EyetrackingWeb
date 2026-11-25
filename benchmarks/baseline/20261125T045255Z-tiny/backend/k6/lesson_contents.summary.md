# k6 summary

scenario: lesson_contents

- http_req_waiting: avg=11.462, min=2.878, med=10.460, max=25.049, p(90)=18.514, p(95)=18.896, p(99)=22.376
- http_req_duration: avg=11.599, min=2.930, med=10.603, max=25.179, p(90)=18.663, p(95)=19.013, p(99)=22.573
- http_req_connecting: p(99)=0.055, avg=0.001, min=0.000, med=0.000, max=0.079, p(90)=0.000, p(95)=0.000
- http_req_sending: avg=0.040, min=0.004, med=0.040, max=0.159, p(90)=0.052, p(95)=0.059, p(99)=0.129
- vus: min=5.000, max=5.000
- http_req_duration{expected_response:true}: med=10.603, max=25.179, p(90)=18.663, p(95)=19.013, p(99)=22.573, avg=11.599, min=2.930
- http_req_receiving: p(90)=0.218, p(95)=0.252, p(99)=0.344, avg=0.097, min=0.009, med=0.067, max=0.362
- iterations: count=238.000, rate=23.406
- http_req_blocked: p(99)=0.076, avg=0.013, min=0.002, med=0.011, max=0.106, p(90)=0.015, p(95)=0.028
- http_req_tls_handshaking: p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000
- http_req_failed: rate=0.000
