# k6 summary

scenario: session_contents

- http_req_failed: rate=0.000
- http_req_sending: max=0.319, p(90)=0.048, p(95)=0.063, p(99)=0.268, avg=0.055, min=0.013, med=0.042
- http_req_waiting: avg=10.141, min=2.725, med=11.676, max=14.563, p(90)=13.532, p(95)=13.687, p(99)=14.388
- http_req_duration: p(90)=13.760, p(95)=13.863, p(99)=14.835, avg=10.311, min=2.779, med=11.919, max=15.079
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: p(95)=13.863, p(99)=14.835, avg=10.311, min=2.779, med=11.919, max=15.079, p(90)=13.760
- http_req_blocked: min=0.006, med=0.011, max=0.107, p(90)=0.018, p(95)=0.039, p(99)=0.094, avg=0.017
- http_req_connecting: avg=0.004, min=0.000, med=0.000, max=0.075, p(90)=0.000, p(95)=0.004, p(99)=0.060
- iterations: count=20.000, rate=4.734
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_receiving: max=0.223, p(90)=0.194, p(95)=0.198, p(99)=0.218, avg=0.116, min=0.027, med=0.114
