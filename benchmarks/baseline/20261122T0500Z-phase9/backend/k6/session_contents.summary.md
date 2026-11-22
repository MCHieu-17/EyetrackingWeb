# k6 summary

scenario: session_contents

- vus: min=5.000, max=5.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_duration: p(95)=19.102, p(99)=23.034, avg=12.073, min=2.960, med=12.634, max=56.362, p(90)=18.411
- http_req_failed: rate=0.000
- iterations: count=238.000, rate=23.310
- http_req_duration{expected_response:true}: avg=12.073, min=2.960, med=12.634, max=56.362, p(90)=18.411, p(95)=19.102, p(99)=23.034
- http_req_sending: min=0.007, med=0.039, max=0.310, p(90)=0.049, p(95)=0.053, p(99)=0.081, avg=0.039
- http_req_waiting: min=2.908, med=12.486, max=56.295, p(90)=18.324, p(95)=18.993, p(99)=22.835, avg=11.927
- http_req_receiving: p(90)=0.228, p(95)=0.261, p(99)=0.349, avg=0.108, min=0.016, med=0.086, max=0.374
- http_req_blocked: med=0.011, max=0.144, p(90)=0.013, p(95)=0.014, p(99)=0.134, avg=0.013, min=0.002
- http_req_connecting: max=0.100, p(90)=0.000, p(95)=0.000, p(99)=0.092, avg=0.002, min=0.000, med=0.000
